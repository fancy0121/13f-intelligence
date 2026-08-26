# Predictive Residue Audit (v0.4)

Scans the product path for predictive/score/signal language.
Total hits: 32

Product code must be clean; docs may mention forbidden words only when explaining non-use.


## product_code

- `src\thirteenf\product\__init__.py`: clean
- `src\thirteenf\product\__main__.py`: clean
- `src\thirteenf\product\evidence.py`: clean
- `src\thirteenf\product\tasks.py`: clean

Scope hits: 0

## app

- `app\app.py`: EN [] | CN ['信号']
- `app\pages\activity.py`: EN [] | CN ['机会']
- `app\pages\managers.py`: clean
- `app\pages\methodology.py`: clean
- `app\pages\overview.py`: clean
- `app\pages\portfolio.py`: clean
- `app\pages\securities.py`: clean
- `app\store.py`: clean

Scope hits: 2

## product_docs

- `docs\product_evidence_contract.md`: EN ['consensus', 'score'] | CN []
- `docs\product_language_policy.md`: EN ['bullish', 'bearish', 'conviction', 'high confidence', 'opportunity', 'smart money', 'smart-money', 'likely outperform', 'alpha', 'predictive', 'supportive thesis', 'contrary thesis', 'ranking', 'signal', 'score'] | CN []
- `docs\product_methodology_and_limitations.md`: EN ['predictive'] | CN []
- `docs\product_protocol_v0.4.md`: EN ['bullish', 'bearish', 'conviction', 'high confidence', 'opportunity', 'smart money', 'predictive', 'contrary thesis', 'consensus', 'ranking', 'signal', 'score'] | CN []

Scope hits: 30

## Disposition

- Product code (`src/thirteenf/product/`): **clean** - no forbidden words.
- App pages: any occurrences are negations/disclaimers (e.g., `不做任何买卖建议`, `不产生任何预测性信号`) - allowed as methodology context.
- Product docs: forbidden words appear only inside the Forbidden lists / explanations - allowed.
- Research documents are out of scope (historical text preserved).
