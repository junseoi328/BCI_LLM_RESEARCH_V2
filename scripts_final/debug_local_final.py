from __future__ import annotations

import json
import sys

from local_ft.inference_final import (
    LocalBCIGenerator,
)


def main():

    initials = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "ㅅㄹㅎ"
    )

    model = (
        LocalBCIGenerator()
    )

    result = (
        model.debug_generate(
            initials,
            16,
        )
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()