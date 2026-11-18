"""Repository entrypoint: python eval.py [--report reports/eval.json]."""
from docguard.evaluation import main

if __name__ == "__main__":
    raise SystemExit(main())
