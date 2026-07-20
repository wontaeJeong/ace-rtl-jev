# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CVDP integration implementation mixins."""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cvdp_integration_support import *


class CVDPSVGuardMixin:
    def _find_matching_sv_block_end(self, text: str, begin_pos: int) -> Optional[int]:
        """Return the end offset of the begin/end block starting at begin_pos."""
        depth = 0
        for match in re.finditer(r"\b(begin|end)\b", text[begin_pos:], flags=re.IGNORECASE):
            token = match.group(1).lower()
            if token == "begin":
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    return begin_pos + match.end()
        return None

    def _local_decl_names(self, block_text: str) -> set[str]:
        """Extract names declared inside a procedural block."""
        names: set[str] = set()
        clean = self._strip_sv_comments(block_text)
        decl_re = re.compile(
            r"(?m)^\s*(?:automatic\s+)?"
            r"(?:logic|reg|bit|integer|int|longint|shortint|time)"
            r"(?:\s+(?:signed|unsigned))?"
            r"(?:\s*\[[^\]]+\])*"
            r"\s+([^;]+);"
        )
        for match in decl_re.finditer(clean):
            for part in match.group(1).split(","):
                part = part.split("=", 1)[0].strip()
                part = re.sub(r"\[[^\]]+\]", "", part).strip()
                name_match = re.match(r"([A-Za-z_][A-Za-z0-9_$]*)\b", part)
                if name_match:
                    names.add(name_match.group(1))
        return names

    def _split_sv_decl_list(self, text: str) -> List[str]:
        """Split a declaration list on top-level commas."""
        parts: List[str] = []
        current: List[str] = []
        depth = 0
        for ch in text:
            if ch in "([{":
                depth += 1
            elif ch in ")]}" and depth > 0:
                depth -= 1
            if ch == "," and depth == 0:
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                continue
            current.append(ch)
        part = "".join(current).strip()
        if part:
            parts.append(part)
        return parts

    def _split_sv_initializer(self, text: str) -> tuple[str, Optional[str]]:
        """Split one declarator into name/dimensions and optional initializer."""
        depth = 0
        for idx, ch in enumerate(text):
            if ch in "([{":
                depth += 1
            elif ch in ")]}" and depth > 0:
                depth -= 1
            elif ch == "=" and depth == 0:
                return text[:idx].strip(), text[idx + 1:].strip()
        return text.strip(), None

    def _replace_sv_identifiers(self, text: str, mapping: Dict[str, str]) -> str:
        """Replace local temporary identifiers inside one procedural block."""
        if not mapping:
            return text
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(name) for name in sorted(mapping, key=len, reverse=True)) + r")\b"
        )
        return pattern.sub(lambda match: mapping[match.group(1)], text)

    def _lift_procedural_declarations_in_block(
        self,
        block_text: str,
        module_index: int,
        block_index: int,
    ) -> tuple[str, List[str]]:
        """
        Move declaration-only procedural temporaries to module scope.

        The configured reasoning model often emits SystemVerilog-style local declarations after a
        reset branch or case item. Icarus in the CVDP native flow rejects those
        placements. Lifting the temporaries is a syntax normalization only; any
        initializer remains a blocking assignment at the original statement.
        """
        decl_line_re = re.compile(
            r"^(?P<indent>\s*)"
            r"(?P<type>(?:automatic\s+)?"
            r"(?:logic|reg|bit|integer|int|longint|shortint|time)"
            r"(?:\s+(?:signed|unsigned))?"
            r"(?:\s*\[[^\]]+\])*)"
            r"\s+(?P<decls>[^;]+);\s*(?://.*)?$"
        )

        lines = block_text.splitlines(keepends=True)
        mapping: Dict[str, str] = {}
        declarations: List[str] = []
        parsed_lines: Dict[int, tuple[re.Match[str], List[tuple[str, Optional[str], str]]]] = {}

        for line_idx, raw_line in enumerate(lines):
            line_body = raw_line.rstrip("\r\n")
            match = decl_line_re.match(line_body)
            if not match:
                continue

            parsed_decls: List[tuple[str, Optional[str], str]] = []
            type_text = re.sub(r"\bautomatic\s+", "", match.group("type")).strip()
            for item in self._split_sv_decl_list(match.group("decls")):
                name_and_dims, initializer = self._split_sv_initializer(item)
                name_match = re.match(
                    r"(?P<name>[A-Za-z_][A-Za-z0-9_$]*)(?P<dims>(?:\s*\[[^\]]+\])*)\s*$",
                    name_and_dims,
                )
                if not name_match:
                    continue
                name = name_match.group("name")
                dims = name_match.group("dims") or ""
                unique_name = mapping.get(name)
                if unique_name is None:
                    unique_name = f"__ace_rtl_tmp_m{module_index}_b{block_index}_{name}"
                    mapping[name] = unique_name
                    declarations.append(f"    {type_text} {unique_name}{dims};")
                parsed_decls.append((name, initializer, unique_name))

            if parsed_decls:
                parsed_lines[line_idx] = (match, parsed_decls)

        if not declarations:
            return block_text, []

        new_lines: List[str] = []
        for line_idx, raw_line in enumerate(lines):
            parsed = parsed_lines.get(line_idx)
            if not parsed:
                new_lines.append(self._replace_sv_identifiers(raw_line, mapping))
                continue

            match, parsed_decls = parsed
            newline = "\n" if raw_line.endswith("\n") else ""
            for _name, initializer, unique_name in parsed_decls:
                if initializer is None:
                    continue
                initializer = self._replace_sv_identifiers(initializer, mapping)
                new_lines.append(f"{match.group('indent')}{unique_name} = {initializer};{newline}")

        return "".join(new_lines), declarations

    def _lift_late_sv_procedural_declarations(self, code: str) -> str:
        """Normalize block-local procedural declarations for the native Icarus flow."""
        if not code:
            return code

        module_re = re.compile(
            r"(?ms)^[ \t]*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b.*?^[ \t]*endmodule\b(?:\s*:\s*[A-Za-z_][A-Za-z0-9_$]*)?"
        )
        matches = list(module_re.finditer(code))
        if not matches:
            module_re = re.compile(
                r"(?ms)\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b.*?\bendmodule\b(?:\s*:\s*[A-Za-z_][A-Za-z0-9_$]*)?"
            )
            matches = list(module_re.finditer(code))
        if not matches:
            return code

        transformed_parts: List[str] = []
        cursor = 0
        total_lifted = 0
        for module_index, module_match in enumerate(matches, start=1):
            transformed_parts.append(code[cursor:module_match.start()])
            module_text = module_match.group(0)
            block_re = re.compile(r"\b(always_ff|always_comb|always_latch|always)\b", re.IGNORECASE)

            module_parts: List[str] = []
            block_cursor = 0
            lifted_decls: List[str] = []
            for block_index, block_match in enumerate(block_re.finditer(module_text), start=1):
                begin_match = re.search(r"\bbegin\b", module_text[block_match.end():], flags=re.IGNORECASE)
                if not begin_match:
                    continue
                begin_pos = block_match.end() + begin_match.start()
                end_pos = self._find_matching_sv_block_end(module_text, begin_pos)
                if end_pos is None:
                    continue
                module_parts.append(module_text[block_cursor:begin_pos])
                new_block, decls = self._lift_procedural_declarations_in_block(
                    module_text[begin_pos:end_pos],
                    module_index,
                    block_index,
                )
                module_parts.append(new_block)
                lifted_decls.extend(decls)
                block_cursor = end_pos

            if lifted_decls:
                module_parts.append(module_text[block_cursor:])
                module_text = "".join(module_parts)
                unique_decls = list(dict.fromkeys(lifted_decls))
                insert_match = re.search(
                    r"(?m)^[ \t]*(?:assign|always_ff|always_comb|always_latch|always|initial)\b",
                    module_text,
                )
                if insert_match:
                    insertion = "\n// Lifted from procedural blocks for CVDP native simulator compatibility.\n"
                    insertion += "\n".join(unique_decls) + "\n"
                    module_text = module_text[:insert_match.start()] + insertion + module_text[insert_match.start():]
                else:
                    module_text = self._replace_first_endmodule(
                        module_text,
                        "\n// Lifted from procedural blocks for CVDP native simulator compatibility.\n"
                        + "\n".join(unique_decls),
                    )
                total_lifted += len(unique_decls)

            transformed_parts.append(module_text)
            cursor = module_match.end()

        transformed_parts.append(code[cursor:])
        if total_lifted:
            self.logger.info(f"Lifted {total_lifted} procedural declaration(s) for CVDP native simulation")
        return "".join(transformed_parts)

    def _enum_body_max_value(self, body: str) -> Optional[int]:
        """Return the largest concrete enum value implied by a typedef body."""
        max_value: Optional[int] = None
        next_value = 0
        for item in body.split(","):
            item = item.strip()
            if not item:
                continue
            name_match = re.match(
                r"([A-Za-z_][A-Za-z0-9_$]*)\s*(?:=\s*([^,]+))?",
                item,
                flags=re.DOTALL,
            )
            if not name_match:
                continue
            value_text = (name_match.group(2) or "").strip()
            if value_text:
                parsed_value = None
                sized = re.match(r"(?:(\d+))?'([bBdDhH])([0-9a-fA-F_xzXZ]+)", value_text)
                plain = re.match(r"\d+", value_text)
                if sized:
                    digits = sized.group(3).replace("_", "")
                    if not re.search(r"[xXzZ]", digits):
                        radix = {"b": 2, "d": 10, "h": 16}.get(sized.group(2).lower(), 10)
                        parsed_value = int(digits, radix)
                elif plain:
                    parsed_value = int(plain.group(0), 10)
                if parsed_value is not None:
                    next_value = parsed_value
            max_value = next_value if max_value is None else max(max_value, next_value)
            next_value += 1
        return max_value

    def _widen_overflowing_sv_enums(self, code: str) -> str:
        """Widen concrete `typedef enum logic [N:0]` ranges that overflow."""
        if not code:
            return code

        widened = 0

        def replace(match: re.Match[str]) -> str:
            nonlocal widened
            msb = int(match.group("msb"))
            lsb = int(match.group("lsb"))
            body = match.group("body")
            max_value = self._enum_body_max_value(body)
            if max_value is None:
                return match.group(0)
            current_width = abs(msb - lsb) + 1
            required_width = max(1, max_value.bit_length())
            if required_width <= current_width:
                return match.group(0)
            if msb >= lsb:
                new_msb = lsb + required_width - 1
                replacement = match.group(0)[: match.start("msb") - match.start()]
                replacement += str(new_msb)
                replacement += match.group(0)[match.end("msb") - match.start():]
            else:
                new_lsb = msb + required_width - 1
                replacement = match.group(0)[: match.start("lsb") - match.start()]
                replacement += str(new_lsb)
                replacement += match.group(0)[match.end("lsb") - match.start():]
            widened += 1
            return replacement

        enum_re = re.compile(
            r"\btypedef\s+enum\s+(?:logic|reg|bit)\s*"
            r"\[\s*(?P<msb>\d+)\s*:\s*(?P<lsb>\d+)\s*\]\s*"
            r"\{(?P<body>.*?)\}",
            flags=re.IGNORECASE | re.DOTALL,
        )
        fixed = enum_re.sub(replace, code)
        if widened:
            self.logger.info(f"Widened {widened} overflowing enum declaration(s) for CVDP native simulation")
        return fixed

    def _enum_typed_variables(self, module_text: str) -> Dict[str, str]:
        """Return module variable -> enum typedef name for enum-typed signals."""
        enum_types = set(
            re.findall(
                r"\btypedef\s+enum\b.*?\}\s*([A-Za-z_][A-Za-z0-9_$]*)\s*;",
                module_text,
                flags=re.IGNORECASE | re.DOTALL,
            )
        )
        if not enum_types:
            return {}

        variables: Dict[str, str] = {}
        for enum_type in enum_types:
            decl_re = re.compile(
                rf"(?m)^[ \t]*(?!typedef\b){re.escape(enum_type)}\s+([^;]+);"
            )
            for match in decl_re.finditer(module_text):
                for item in self._split_sv_decl_list(match.group(1)):
                    name_and_dims, _initializer = self._split_sv_initializer(item)
                    name_match = re.match(r"([A-Za-z_][A-Za-z0-9_$]*)\b", name_and_dims.strip())
                    if name_match:
                        variables[name_match.group(1)] = enum_type
        return variables

    def _cast_enum_ternary_assignments(self, code: str) -> str:
        """Add explicit enum casts for ternary assignments rejected by Icarus."""
        if not code:
            return code

        module_re = re.compile(
            r"(?ms)^[ \t]*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b.*?^[ \t]*endmodule\b(?:\s*:\s*[A-Za-z_][A-Za-z0-9_$]*)?"
        )
        matches = list(module_re.finditer(code))
        if not matches:
            module_re = re.compile(
                r"(?ms)\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b.*?\bendmodule\b(?:\s*:\s*[A-Za-z_][A-Za-z0-9_$]*)?"
            )
            matches = list(module_re.finditer(code))
        if not matches:
            return code

        cast_count = 0
        parts: List[str] = []
        cursor = 0

        for module_match in matches:
            parts.append(code[cursor:module_match.start()])
            module_text = module_match.group(0)
            enum_vars = self._enum_typed_variables(module_text)
            for var_name, enum_type in enum_vars.items():
                assign_re = re.compile(
                    rf"\b(?P<var>{re.escape(var_name)})\s*(?P<op><=|=)\s*"
                    r"(?P<wrapped>\((?P<expr1>[^;\n]*\?[^;\n]*:[^;\n]*)\)|(?P<expr2>[^;\n()]*\?[^;\n]*:[^;\n]*))\s*;",
                )

                def replace(match: re.Match[str]) -> str:
                    nonlocal cast_count
                    expr = (match.group("expr1") or match.group("expr2") or "").strip()
                    if "'(" in expr:
                        return match.group(0)
                    cast_count += 1
                    return f"{match.group('var')} {match.group('op')} {enum_type}'({expr});"

                module_text = assign_re.sub(replace, module_text)
            parts.append(module_text)
            cursor = module_match.end()

        parts.append(code[cursor:])
        if cast_count:
            self.logger.info(f"Added {cast_count} enum ternary cast(s) for CVDP native simulation")
        return "".join(parts)

    def _generated_code_sv_semantic_guard_report(self, code: str) -> Optional[str]:
        """
        Catch common simulator-visible RTL semantic mistakes before an expensive CVDP run.

        This is a structural RTL hygiene guard, not a functional oracle. In
        particular, assigning block-local temporary variables with nonblocking
        assignments inside always_ff commonly feeds stale/default values into
        same-cycle pipeline updates. The HDBN runs repeatedly hit this pattern.
        """
        if not code:
            return None

        clean = self._strip_sv_comments(code)
        violations: List[str] = []
        block_re = re.compile(r"\b(always_ff|always_comb|always_latch|always)\b", re.IGNORECASE)
        decl_line_re = re.compile(
            r"^\s*(?:automatic\s+)?"
            r"(?:logic|reg|bit|integer|int|longint|shortint|time)"
            r"(?:\s+(?:signed|unsigned))?"
            r"(?:\s*\[[^\]]+\])*"
            r"\s+[A-Za-z_][A-Za-z0-9_$]*"
        )

        for idx, match in enumerate(block_re.finditer(clean), start=1):
            begin_match = re.search(r"\bbegin\b", clean[match.end():], flags=re.IGNORECASE)
            if not begin_match:
                continue
            begin_pos = match.end() + begin_match.start()
            end_pos = self._find_matching_sv_block_end(clean, begin_pos)
            if end_pos is None:
                continue
            block_text = clean[begin_pos:end_pos]
            block_kind = match.group(1)

            seen_executable = False
            late_decls: List[str] = []
            for line_no, raw_line in enumerate(block_text.splitlines(), start=1):
                line = raw_line.strip()
                if not line or line in {"begin", "end"} or line.startswith("end "):
                    continue
                is_decl = bool(decl_line_re.match(line))
                if is_decl:
                    if seen_executable:
                        late_decls.append(f"line+{line_no}: `{line[:96]}`")
                    continue
                # The outer block's begin/end tokens are not statements, but
                # nested if/case/for blocks are procedural control statements.
                seen_executable = True

            if late_decls:
                violations.append(
                    f"{block_kind} block {idx} declares variable(s) after procedural statements "
                    "(Icarus rejects declarations inside nested if/case/for blocks): "
                    + "; ".join(late_decls[:4])
                )

            runaway_terms = sorted(set(re.findall(
                r"\b(while|forever|break|continue|disable)\b",
                block_text,
                flags=re.IGNORECASE,
            )))
            if runaway_terms:
                violations.append(
                    f"{block_kind} block {idx} uses procedural construct(s) "
                    + ", ".join(f"`{term}`" for term in runaway_terms[:8])
                    + ". CVDP cocotb waits on finite handshakes; replace data-dependent or "
                    "escape-based loops with bounded `for` loops, explicit FSM states, or "
                    "fixed counters so every transaction terminates"
                )

            if block_kind.lower() == "always_ff":
                local_names = self._local_decl_names(block_text)
                if not local_names:
                    continue
                nba_locals = sorted(
                    name for name in local_names
                    if re.search(rf"\b{re.escape(name)}\s*<=", block_text)
                )
                if nba_locals:
                    violations.append(
                        f"always_ff block {idx} assigns block-local temporary variable(s) "
                        "with nonblocking `<=`: "
                        + ", ".join(f"`{name}`" for name in nba_locals[:12])
                    )

        for enum_match in re.finditer(
            r"\btypedef\s+enum\s+(?:logic|reg|bit)?\s*"
            r"(?:\[\s*(?P<msb>\d+)\s*:\s*(?P<lsb>\d+)\s*\])?\s*"
            r"\{(?P<body>.*?)\}",
            clean,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            body = enum_match.group("body")
            enum_width = None
            if enum_match.group("msb") is not None and enum_match.group("lsb") is not None:
                msb = int(enum_match.group("msb"))
                lsb = int(enum_match.group("lsb"))
                enum_width = abs(msb - lsb) + 1
            enum_max = (1 << enum_width) - 1 if enum_width is not None else None
            explicit_values: dict[int, list[str]] = {}
            overflow_names: List[str] = []
            next_value = 0
            for item in body.split(","):
                item = item.strip()
                if not item:
                    continue
                name_match = re.match(
                    r"([A-Za-z_][A-Za-z0-9_$]*)\s*(?:=\s*([^,]+))?",
                    item,
                    flags=re.DOTALL,
                )
                if not name_match:
                    continue
                name = name_match.group(1)
                value_text = (name_match.group(2) or "").strip()
                if value_text:
                    parsed_value = None
                    sized = re.match(r"(?:(\d+))?'[bBdDhH]([0-9a-fA-F_xzXZ]+)", value_text)
                    plain = re.match(r"\d+", value_text)
                    if sized:
                        digits = sized.group(2).replace("_", "")
                        if not re.search(r"[xXzZ]", digits):
                            base = value_text.lower().split("'")[-1][0]
                            radix = {"b": 2, "d": 10, "h": 16}.get(base, 10)
                            parsed_value = int(digits, radix)
                    elif plain:
                        parsed_value = int(plain.group(0), 10)
                    if parsed_value is not None:
                        next_value = parsed_value
                stored_value = next_value
                if enum_max is not None and next_value > enum_max:
                    overflow_names.append(name)
                    stored_value = next_value & enum_max
                explicit_values.setdefault(stored_value, []).append(name)
                next_value += 1

            duplicate_groups = [names for names in explicit_values.values() if len(names) > 1]
            if overflow_names:
                width_text = f"{enum_width}-bit" if enum_width is not None else "fixed-width"
                violations.append(
                    f"typedef enum uses a {width_text} state vector that is too narrow; inferred "
                    "state value(s) overflow for "
                    + ", ".join(f"`{name}`" for name in overflow_names[:8])
                    + ". Increase the enum vector width or assign explicit unique encodings"
                )
            if duplicate_groups:
                violations.append(
                    "typedef enum declares duplicate state encodings that Icarus treats as an error: "
                    + "; ".join(", ".join(f"`{name}`" for name in names[:6]) for names in duplicate_groups[:4])
                    + ". Increase the enum vector width or assign unique state values"
                )

        hdbn_decoder = self._module_text_from_candidate(clean, ["hdbn_decoder_core"])
        hdbn_decoder_has_five_visible_pipe = False
        if hdbn_decoder:
            decoder_clean = self._strip_sv_comments(hdbn_decoder)
            hdbn_decoder_has_five_visible_pipe = bool(
                re.search(r"\blogic\s*\[\s*4\s*:\s*0\s*\]\s+data_pipe\b", decoder_clean)
                and re.search(r"\bassign\s+data_out\s*=\s*data_pipe\s*\[\s*4\s*\]\s*;", decoder_clean)
            )
            has_six_stage_decoder_pipe = bool(
                re.search(r"\blocalparam\s+(?:integer|int)?\s*(?:PIPE_DEPTH|DECODER_LATENCY)\s*=\s*6\b", decoder_clean)
                or re.search(r"\blogic\s*\[\s*5\s*:\s*0\s*\]\s+data_pipe\b", decoder_clean)
            )
            registers_decoder_inputs = bool(
                re.search(r"\b[A-Za-z_][A-Za-z0-9_$]*\s*<=\s*p_in\b", decoder_clean)
                and re.search(r"\b[A-Za-z_][A-Za-z0-9_$]*\s*<=\s*n_in\b", decoder_clean)
            )
            normalizes_inputs_with_nba = bool(
                re.search(r"\bp_norm\s*<=\s*\(?\s*p_in\b|\bp_norm\s*<=\s*\([^;]*p_in", decoder_clean)
                or re.search(r"\bn_norm\s*<=\s*\(?\s*n_in\b|\bn_norm\s*<=\s*\([^;]*n_in", decoder_clean)
            )
            registers_old_pipe_tail_to_output = bool(
                re.search(r"\bdata_out\s*<=\s*data_pipe\s*\[", decoder_clean)
            )

            if has_six_stage_decoder_pipe and registers_decoder_inputs:
                violations.append(
                    "hdbn_decoder_core registers `p_in/n_in` and also uses a six-stage decoded-data pipe; "
                    "the public decoder-only test measures exactly six clock edges from driven `p_in/n_in` "
                    "to `data_out`, so this structure usually adds a seventh cycle"
                )
            if normalizes_inputs_with_nba:
                violations.append(
                    "hdbn_decoder_core normalizes `p_in/n_in` into `p_norm/n_norm` with nonblocking `<=` "
                    "inside a clocked block; same-block decode then sees the previous cycle's pulse. "
                    "Normalize current inputs with blocking temporaries before computing `decoded_bit`"
                )
            if registers_old_pipe_tail_to_output:
                violations.append(
                    "hdbn_decoder_core assigns `data_out <= data_pipe[...]` from the old pipe tail while "
                    "also shifting the decoded-data pipe in the same clocked block; this adds a hidden "
                    "output cycle in the public latency path. Drive `data_out` directly from the pipe tail "
                    "or compute the exact post-shift output value in the same clock"
                )
            if re.search(r"\blogic\s*\[\s*5\s*:\s*0\s*\]\s+data_pipe\b", decoder_clean) and re.search(
                r"\bassign\s+data_out\s*=\s*data_pipe\s*\[\s*5\s*\]\s*;", decoder_clean
            ):
                violations.append(
                    "hdbn_decoder_core uses a six-bit continuous decoded-data pipe (`data_pipe[5]`). "
                    "The public cocotb decoder-only test reads immediately after `RisingEdge`, so this "
                    "is observed one cycle late; use a five-bit continuous pipe (`logic [4:0] data_pipe; "
                    "assign data_out = data_pipe[4];`)"
                )

        hdbn_modules = [
            text for names in (["hdbn_encoder_core"], ["hdbn_decoder_core"], ["hdbn_encoder"], ["hdbn_decoder"])
            for text in [self._module_text_from_candidate(clean, names)]
            if text
        ]
        for module_text in hdbn_modules:
            module_clean = self._strip_sv_comments(module_text)
            module_header = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)", module_clean)
            module_name = module_header.group(1) if module_header else "HDBN module"
            narrow_counters = sorted(set(re.findall(
                r"(?m)^\s*logic\s+"
                r"(zero_(?:run|cnt|count)|[A-Za-z_][A-Za-z0-9_$]*zero(?:_run|_cnt|_count))\s*;",
                module_clean,
            )))
            compared_to_encoder_type = [
                name for name in narrow_counters
                if re.search(rf"\b{re.escape(name)}\s*(?:==|>=|>|<|<=)\s*(?:encoder_type|ZERO_LIMIT)\b", module_clean)
            ]
            if compared_to_encoder_type:
                violations.append(
                    f"{module_name} declares one-bit HDBN zero counter(s) "
                    + ", ".join(f"`{name}`" for name in compared_to_encoder_type[:8])
                    + "; these counters must count at least 0..encoder_type, otherwise HDB2/HDB3 "
                    "substitution never triggers at encoder_type=2/3"
                )

            if re.search(r"\bzero_(?:run|cnt|count)\s*==\s*ZERO_LIMIT\s*\+\s*1\b", module_clean):
                violations.append(
                    f"{module_name} triggers HDBN zero substitution at `ZERO_LIMIT + 1`; the public "
                    "contract requires a substitution pulse after exactly `encoder_type` previous "
                    "no-pulse zeros, so the trigger threshold is `ZERO_LIMIT`"
                )
            if re.search(r"\bzero_(?:run|cnt|count)\s*==\s*ZERO_LIMIT\s*-\s*1\b", module_clean):
                violations.append(
                    f"{module_name} triggers HDBN zero substitution at `ZERO_LIMIT - 1`; that emits "
                    "the substitution pulse one zero early. Use the public threshold `ZERO_LIMIT`"
                )

            if "encoder" in module_name.lower():
                delay_param_names = set(re.findall(
                    r"\blocalparam\s+(?:integer|int)?\s*([A-Za-z_][A-Za-z0-9_$]*)\s*=\s*"
                    r"2\s*\*\s*encoder_type\s*-\s*1\b",
                    module_clean,
                ))
                for delay_name in sorted(delay_param_names):
                    old_tail_shift = bool(
                        re.search(
                            rf"\b(?:data_pipe|data_delay)\s*<=\s*\{{\s*(?:data_pipe|data_delay)\s*\[\s*{re.escape(delay_name)}\s*-\s*2\s*:\s*0\s*\]\s*,\s*data_in\s*\}}",
                            module_clean,
                        )
                        and re.search(
                            rf"\b[A-Za-z_][A-Za-z0-9_$]*(?:delayed|current)?_?bit\s*=\s*(?:data_pipe|data_delay)\s*\[\s*{re.escape(delay_name)}\s*-\s*1\s*\]",
                            module_clean,
                        )
                    )
                    if old_tail_shift and not hdbn_decoder_has_five_visible_pipe:
                        violations.append(
                            f"{module_name} uses old-tail nonblocking shift style with `{delay_name} = 2*encoder_type - 1`; "
                            "pair this style with the public five-bit continuous decoder pipe, or compute "
                            "the delayed bit from the post-shift vector to avoid an observed loopback latency mismatch"
                        )

                stale_delay_names = sorted(set(re.findall(
                    r"\b([A-Za-z_][A-Za-z0-9_$]*(?:delayed|current)?_?bit)\s*<=\s*"
                    r"(?:[A-Za-z_][A-Za-z0-9_$]*(?:data_pipe|data_delay)|(?:data_pipe|data_delay))\s*\[",
                    module_clean,
                )))
                stale_delay_names = [
                    name for name in stale_delay_names
                    if re.search(rf"\bif\s*\(\s*{re.escape(name)}\s*\)", module_clean)
                ]
                if stale_delay_names:
                    violations.append(
                        f"{module_name} assigns delayed symbol temporary "
                        + ", ".join(f"`{name}`" for name in stale_delay_names[:8])
                        + " with nonblocking `<=` and uses it in the same clocked block; "
                        "this adds a hidden encoder cycle. Compute the delayed symbol with "
                        "blocking `=` from the current pipe tail before encoding"
                    )

            if "decoder" in module_name.lower():
                polarity_terms = (
                    r"(?:polarity_now|pulse_polarity|current_polarity|"
                    r"polarity|p_now|n_now|p_active|n_active)"
                )
                last_polarity_terms = (
                    r"(?:last_polarity|last_pulse_polarity|last_pulse_pol|"
                    r"last_nonzero_polarity|prev_polarity|previous_polarity)"
                )
                has_polarity_discriminator = bool(
                    re.search(rf"\b{polarity_terms}\b\s*(?:==|!=)\s*\b{last_polarity_terms}\b", module_clean)
                    or re.search(rf"\b{last_polarity_terms}\b\s*(?:==|!=)\s*\b{polarity_terms}\b", module_clean)
                    or re.search(r"\b(?:same_polarity|is_violation|violation_pulse|legal_violation)\b\s*=", module_clean)
                )
                zero_run_pulse_as_zero = False
                for zero_block in re.finditer(
                    r"\bif\s*\(\s*(?:zero_run|zero_cnt|zero_count)\s*==\s*(?:ZERO_LIMIT|encoder_type)\s*\)\s*begin(?P<body>.{0,700}?)\bend\b",
                    module_clean,
                    flags=re.DOTALL,
                ):
                    body = zero_block.group("body")
                    if re.search(r"\b(?:decoded_bit|next_decoded|decoded)\s*(?:=|<=)\s*1'b0\b", body):
                        zero_run_pulse_as_zero = True
                        break
                if (
                    not zero_run_pulse_as_zero
                    and re.search(
                        r"\b(?:decoded_bit|next_decoded|decoded)\s*(?:=|<=)\s*"
                        r"\(\s*(?:zero_run|zero_cnt|zero_count)\s*==\s*(?:ZERO_LIMIT|encoder_type)\s*\)\s*\?\s*1'b0\s*:\s*1'b1",
                        module_clean,
                    )
                ):
                    zero_run_pulse_as_zero = True
                if zero_run_pulse_as_zero and not has_polarity_discriminator:
                    violations.append(
                        f"{module_name} decodes any single pulse after exactly `encoder_type` no-pulse symbols "
                        "as zero without checking AMI/violation polarity. That misdecodes legal data sequences "
                        "with `encoder_type` zeros followed by a real `1`; only a distinguishable HDBn "
                        "substitution/violation marker should decode as zero"
                    )

        if not violations:
            return None

        return (
            "CVDP_RTL_SEMANTIC_GUARD: generated RTL has simulator-visible clocked-block temporary assignment hazards.\n"
            + "\n".join(f"- {item}" for item in violations[:12])
            + "\nFix: declare all procedural temporary variables at module scope or at the very top of the outer procedural block before any `if`, `case`, assignment, or loop; assign local temporaries in `always_ff` with blocking `=`, reserve nonblocking `<=` for persistent registers/signals declared at module scope, give enum states unique encodings, replace unbounded/escape-based loops with bounded counters or FSM states, make HDBN zero counters wide enough to count through `encoder_type`, and distinguish ordinary AMI data pulses from legal HDBn substitution/violation markers."
        )


