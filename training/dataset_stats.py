from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from training_v2.common import read_jsonl


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--train", default="training_v2/data/train_semantic_v2.jsonl")
    p.add_argument("--dev", default="training_v2/data/dev_semantic_v2.jsonl")
    p.add_argument("--hard", default="training_v2/data/hard50_v2.jsonl")
    args = p.parse_args()

    train = read_jsonl(args.train)
    dev = read_jsonl(args.dev)
    hard = read_jsonl(args.hard)

    def summarize(rows, name):
        print("="*72)
        print(name, "N=", len(rows))
        if rows and "initials" in rows[0]:
            print("initial groups=", len({x["initials"] for x in rows}))
            print("category=", Counter(x.get("category","") for x in rows))
            print(
                "mean candidates=",
                sum(len(x.get("candidates",[])) for x in rows)/len(rows),
            )
        else:
            print("initial groups=", len({x["bci_input"] for x in rows}))
            print("category=", Counter(x.get("category","") for x in rows))

    summarize(train, "TRAIN")
    summarize(dev, "DEV")
    summarize(hard, "HARD")


if __name__ == "__main__":
    main()
