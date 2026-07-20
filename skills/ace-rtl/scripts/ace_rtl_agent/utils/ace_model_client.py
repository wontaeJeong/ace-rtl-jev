# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
ACE-RTL API Client - Interface for the custom ACE-RTL model API
"""

import json
import requests
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class AceRTLMessage:
    """Message for ACE-RTL API"""
    role: str
    content: str


class AceRTLClient:
    """
    Client for interacting with the ACE-RTL custom model API.

    This client handles API calls to the custom ACE-RTL model endpoint
    with proper error handling and retry logic.
    """

    def __init__(self, api_url: str = "http://10.49.133.52:8000/v1/chat/completions",
                 model_name: str = "ace_rtl-v1", logger=None,
                 max_retries: int = 3, initial_backoff: float = 5.0,
                 connect_timeout: int = 30, max_time: int = 300,
                 temperature: float = 0.2):
        """
        Initialize ACE-RTL API client.

        Args:
            api_url: ACE-RTL API endpoint URL
            model_name: Model name to use (default: "ace_rtl-v1")
            logger: Logger instance
            max_retries: Maximum number of retries for API calls
            initial_backoff: Initial backoff time in seconds
            connect_timeout: Connection timeout in seconds
            max_time: Maximum request time in seconds
            temperature: Default temperature for API calls (default: 0.2)
        """
        self.api_url = api_url
        self.model_name = model_name
        self.logger = logger
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.connect_timeout = connect_timeout
        self.max_time = max_time
        self.default_temperature = temperature

        if self.logger:
            self.logger.info(f"ACE-RTL client initialized: {api_url}, model: {model_name}, temperature: {temperature}")

    def call_llm(self, prompt: str, max_tokens: int = 8192, temperature: float = None) -> Optional[str]:
        """
        Call the ACE-RTL model with a prompt.

        Args:
            prompt: Input prompt for the model
            max_tokens: Maximum tokens to generate (default: 8192 for this compatibility client)
            temperature: Temperature for generation (uses default_temperature if not specified)

        Returns:
            Generated response text or None if failed
        """
        if temperature is None:
            temperature = self.default_temperature
        messages = [AceRTLMessage(role="user", content=prompt)]
        return self.call_llm_with_messages(messages, max_tokens, temperature)

    def call_llm_with_messages(self, messages: List[AceRTLMessage],
                              max_tokens: int = 8192, temperature: float = None) -> Optional[str]:
        """
        Call the ACE-RTL model with a list of messages.

        Args:
            messages: List of messages for the conversation
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation (uses default_temperature if not specified)

        Returns:
            Generated response text or None if failed
        """
        if temperature is None:
            temperature = self.default_temperature
        # Prepare the request payload
        payload = {
            "model": self.model_name,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Retry loop with exponential backoff
        backoff_time = self.initial_backoff

        for attempt in range(self.max_retries + 1):
            try:
                if self.logger:
                    self.logger.info(f"ACE-RTL API call attempt {attempt + 1}/{self.max_retries + 1}")

                # Make the API request
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=(self.connect_timeout, self.max_time)
                )

                # Check if request was successful
                if response.status_code == 200:
                    try:
                        response_data = response.json()

                        # Extract the generated content
                        if "choices" in response_data and len(response_data["choices"]) > 0:
                            content = response_data["choices"][0].get("message", {}).get("content", "")

                            if self.logger:
                                self.logger.info(f"ACE-RTL API call successful, response length: {len(content)} chars")

                            return content
                        else:
                            if self.logger:
                                self.logger.error("ACE-RTL API response missing choices or content")
                            return None

                    except json.JSONDecodeError as e:
                        if self.logger:
                            self.logger.error(f"Failed to parse ACE-RTL API response JSON: {e}")
                        return None

                else:
                    if self.logger:
                        self.logger.warning(f"ACE-RTL API call failed with status {response.status_code}: {response.text}")

                    # If this is the last attempt, return None
                    if attempt == self.max_retries:
                        return None

            except requests.exceptions.Timeout as e:
                if self.logger:
                    self.logger.warning(f"ACE-RTL API call timeout (attempt {attempt + 1}): {e}")

            except requests.exceptions.ConnectionError as e:
                if self.logger:
                    self.logger.warning(f"ACE-RTL API connection error (attempt {attempt + 1}): {e}")

            except requests.exceptions.RequestException as e:
                if self.logger:
                    self.logger.warning(f"ACE-RTL API request error (attempt {attempt + 1}): {e}")

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Unexpected error in ACE-RTL API call (attempt {attempt + 1}): {e}")

            # If this wasn't the last attempt, wait before retrying
            if attempt < self.max_retries:
                if self.logger:
                    self.logger.info(f"Retrying ACE-RTL API call in {backoff_time:.1f} seconds...")
                time.sleep(backoff_time)
                backoff_time *= 2  # Exponential backoff

        if self.logger:
            self.logger.error("ACE-RTL API call failed after all retry attempts")
        return None

    def prompt(self, prompt: str, schema=None, prompt_log=None, files=None, timeout=None, category=None, task_id=None, temperature: float = None):
        """
        CVDP-compatible prompt method that matches LLMBackend interface.

        Args:
            prompt: The prompt text
            schema: Schema for structured output (ignored for ACE-RTL)
            prompt_log: Log file path (ignored for ACE-RTL)
            files: File attachments (ignored for ACE-RTL)
            timeout: Request timeout (ignored, uses internal timeout)
            category: Category ID (ignored for ACE-RTL)
            task_id: Task ID (ignored for ACE-RTL)
            temperature: Temperature for generation (uses default_temperature if not specified)

        Returns:
            Tuple of (response_text, success_boolean)
        """
        if temperature is None:
            temperature = self.default_temperature
        try:
            if self.logger:
                self.logger.info(f"DEBUG: ACE-RTL prompt called with files={files}, schema={schema}, task_id={task_id}")
                self.logger.info(f"DEBUG: Prompt length: {len(prompt)} chars")

            # Format prompt for Qwen chat format (like previous successful ACE-RTL runs)
            formatted_prompt = f"<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\n\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

            if self.logger:
                self.logger.info(f"DEBUG: Formatted prompt length: {len(formatted_prompt)} chars")

            raw_response = self.call_llm(formatted_prompt, max_tokens=8192, temperature=temperature)

            if self.logger:
                self.logger.info(f"DEBUG: Raw ACE-RTL response length: {len(raw_response) if raw_response else 0} chars")
                if raw_response:
                    self.logger.info(f"DEBUG: Response starts with: {raw_response[:100]}...")
                    self.logger.info(f"DEBUG: Response ends with: ...{raw_response[-100:]}")

            if raw_response and raw_response.strip():
                # Return raw response and let CVDP handle ALL processing
                # This matches exactly how LLM model works - it returns raw content
                # and then CVDP calls parse_model_response on it
                if self.logger:
                    self.logger.info(f"DEBUG: Returning raw ACE-RTL response ({len(raw_response)} chars) for CVDP to process")
                    self.logger.info(f"DEBUG: Response starts with: {raw_response[:200]}...")
                    self.logger.info(f"DEBUG: Response ends with: ...{raw_response[-200:]}")
                    self.logger.info(f"DEBUG: Files parameter: {files}")
                    self.logger.info(f"DEBUG: Schema parameter: {schema}")
                    self.logger.info(f"DEBUG: no_schema would be: {files and len(files) == 1 and schema is None}")
                    self.logger.info(f"DEBUG: files check: {files is not None}, len(files)==1: {len(files) == 1 if files else False}, schema is None: {schema is None}")

                # Parse the response like LLM does - call parse_model_response internally
                # This creates the proper {"direct_text": content} structure CVDP expects

                # Simulate CVDP's parse_model_response logic for single file direct text mode
                expected_single_file = files and len(files) == 1 and schema is None

                if expected_single_file:
                    # Single file direct text mode - create the structure CVDP expects
                    parsed_output = {"direct_text": raw_response.strip()}
                    if self.logger:
                        self.logger.info(f"DEBUG: Created parsed output for single file mode: {len(raw_response)} chars")
                        self.logger.info(f"DEBUG: Parsed output keys: {list(parsed_output.keys())}")
                    return parsed_output, True
                else:
                    # Multi-file or schema mode - return raw for JSON parsing
                    if self.logger:
                        self.logger.info(f"DEBUG: Returning raw response for multi-file/schema mode")
                    return raw_response.strip(), True
            else:
                if self.logger:
                    self.logger.error(f"DEBUG: ACE-RTL returned empty or None response")
                return "", False
        except Exception as e:
            if self.logger:
                self.logger.error(f"ACE-RTL prompt failed: {str(e)}")
            return "", False


    def test_connection(self) -> bool:
        """
        Test connection to the ACE-RTL API.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            response = self.call_llm("Hello, can you respond?", max_tokens=50, temperature=0.1)
            return response is not None and len(response.strip()) > 0
        except Exception as e:
            if self.logger:
                self.logger.error(f"ACE-RTL connection test failed: {e}")
            return False
