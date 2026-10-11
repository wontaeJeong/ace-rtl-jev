"""Cross-process inference admission. Missing campaign disables network inference.

Request caps are exact; token/currency charges include conservative reservations
for unknown billing. Opaque provider charges need provider-side limits to obtain
an unconditional financial guarantee. No primary price is fabricated.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import uuid
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path


class BudgetDenied(RuntimeError):
    def __init__(self,reason):
        directory=os.environ.get('ACE_EXPERIMENT_TELEMETRY')
        if directory:
            path=Path(directory)/('budget-denied-'+uuid.uuid4().hex+'.json')
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'event':'budget_denied','reason':reason,'case_id':os.environ.get('ACE_EXPERIMENT_CASE_ID')}))
            temporary.replace(path)
        super().__init__('NON_RETRYABLE: inference budget denied: '+reason)


def money_units(value) -> int:
    try:
        number=Decimal(str(value))
        if not number.is_finite() or number<0 or number>1000000:raise ValueError('Invalid currency budget')
        return int((number*1000000000).to_integral_value(rounding=ROUND_CEILING))
    except (InvalidOperation,TypeError):raise ValueError('Invalid currency budget') from None


def normalise(limits: dict) -> dict:
    if set(limits)!= {'primary','jev'}:raise ValueError('Budget must define primary and jev')
    result={}
    for provider,values in limits.items():
        for field in ('max_calls','max_tokens'):
            n=values.get(field)
            if not isinstance(n,int) or isinstance(n,bool) or not 0<n<=1000000000:
                raise ValueError('Invalid budget '+field)
        item={k:values[k] for k in ('max_calls','max_tokens')}
        if provider=='jev':
            item['max_money']=money_units(values['max_usd'])
            item['reserve_money']=money_units(values['reserve_usd'])
            if not 0<item['reserve_money']<=item['max_money']:raise ValueError('Invalid JEV currency reservation')
        result[provider]=item
    return result


def init_budget(path: Path, limits: dict) -> None:
    canonical=json.dumps(normalise(limits),sort_keys=True)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path,timeout=30) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, provider TEXT NOT NULL, reserved_tokens INTEGER NOT NULL, token_charge INTEGER NOT NULL, reserved_money INTEGER NOT NULL, money_charge INTEGER NOT NULL, status TEXT NOT NULL, tokens_known INTEGER NOT NULL, money_known INTEGER NOT NULL)')
        existing=db.execute("SELECT value FROM meta WHERE key='limits'").fetchone()
        if existing and existing[0]!=canonical:raise ValueError('Campaign limits are immutable')
        if not existing:
            db.execute("INSERT INTO meta VALUES ('limits',?)",(canonical,))
            db.execute("INSERT INTO meta VALUES ('closed','0')")
            db.execute("INSERT INTO meta VALUES ('denied','0')")


def open_budget(path: Path):
    if not path.is_file():raise BudgetDenied('missing campaign file')
    db=sqlite3.connect(path,timeout=30)
    try:
        limits=json.loads(db.execute("SELECT value FROM meta WHERE key='limits'").fetchone()[0])
        return db,limits
    except (sqlite3.Error,TypeError,ValueError):
        db.close();raise BudgetDenied('invalid campaign file') from None


def reserve(provider: str, input_text: str, output_tokens: int) -> dict:
    raw=os.environ.get('ACE_EXPERIMENT_BUDGET_FILE')
    if not raw:raise BudgetDenied('ACE_EXPERIMENT_BUDGET_FILE is required')
    if provider not in ('primary','jev') or not isinstance(output_tokens,int) or isinstance(output_tokens,bool) or output_tokens<0:
        raise ValueError('Invalid inference reservation')
    path=Path(raw).resolve();db,limits=open_budget(path)
    tokens=len(input_text.encode('utf-8'))+4096+output_tokens
    error=None;ticket_id=uuid.uuid4().hex
    try:
        db.execute('BEGIN IMMEDIATE')
        limit=limits[provider]
        calls,charged,cost=db.execute('SELECT count(*),coalesce(sum(token_charge),0),coalesce(sum(money_charge),0) FROM tickets WHERE provider=?',(provider,)).fetchone()
        closed=db.execute("SELECT value FROM meta WHERE key='closed'").fetchone()[0]=='1'
        money=limit.get('reserve_money',0)
        if closed:error='campaign closed after reservation overrun'
        elif calls>=limit['max_calls']:error=provider+' request cap reached'
        elif charged+tokens>limit['max_tokens']:error=provider+' token reservation cap reached'
        elif provider=='jev' and cost+money>limit['max_money']:error='JEV currency exposure cap reached'
        if error:
            db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='denied'")
        else:
            db.execute('INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?)',(ticket_id,provider,tokens,tokens,money,money,'inflight',0,0))
        db.commit()
    finally:db.close()
    if error:raise BudgetDenied(error)
    return {'id':ticket_id,'path':str(path),'provider':provider}


def settle(ticket: dict, usage: dict | None) -> None:
    db,limits=open_budget(Path(ticket['path']))
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT provider,reserved_tokens,reserved_money,status FROM tickets WHERE id=?',(ticket['id'],)).fetchone()
        if not row or row[3]!='inflight':raise ValueError('Reservation already settled or missing')
        provider,tokens,money,_=row
        token_known=bool(usage and usage.get('source')=='reported' and isinstance(usage.get('total_tokens'),int) and not isinstance(usage['total_tokens'],bool) and usage['total_tokens']>=0)
        token_charge=usage['total_tokens'] if token_known else tokens
        cost_known=bool(provider=='jev' and usage and usage.get('cost_currency')=='USD' and usage.get('provider_cost') is not None)
        cost_charge=money_units(usage['provider_cost']) if cost_known else money
        if token_charge>tokens or cost_charge>money:
            db.execute("UPDATE meta SET value='1' WHERE key='closed'")
        db.execute('UPDATE tickets SET token_charge=?,money_charge=?,status=?,tokens_known=?,money_known=? WHERE id=?',
                   (token_charge,cost_charge,'settled' if token_known else 'unknown_usage',int(token_known),int(cost_known),ticket['id']))
        db.commit()
    finally:db.close()


def snapshot(path: Path) -> dict:
    db,limits=open_budget(Path(path))
    try:
        result={'limits':limits,'closed':db.execute("SELECT value FROM meta WHERE key='closed'").fetchone()[0]=='1',
                'denied':int(db.execute("SELECT value FROM meta WHERE key='denied'").fetchone()[0])}
        for provider in limits:
            calls,tokens,cost,known,unknown=db.execute('SELECT count(*),coalesce(sum(token_charge),0),coalesce(sum(money_charge),0),coalesce(sum(CASE WHEN tokens_known=1 THEN token_charge ELSE 0 END),0),coalesce(sum(CASE WHEN tokens_known=0 THEN 1 ELSE 0 END),0) FROM tickets WHERE provider=?',(provider,)).fetchone()
            result[provider]={'calls':calls,'token_charge':tokens,'known_tokens':known,'unknown_token_reservations':unknown,
                              'usd_exposure':cost/1e9 if provider=='jev' else None}
        return result
    finally:db.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path',type=Path);parser.add_argument('--init',action='store_true')
    args=parser.parse_args()
    if args.init:init_budget(args.path,{'primary':{'max_calls':12,'max_tokens':300000},'jev':{'max_calls':64,'max_tokens':1000000,'max_usd':0.10,'reserve_usd':0.0015}})
    print(json.dumps(snapshot(args.path),indent=2))
