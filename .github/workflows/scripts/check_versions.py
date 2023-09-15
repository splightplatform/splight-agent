import operator
import sys


class VersionError(Exception):
    """Raised when the compared values don't match."""


OPERATORS = {"gt": operator.gt, "lt": operator.lt, "eq": operator.eq}


class VersionObject:
    def __init__(self, version_string):
        self.parsed = tuple(map(int, version_string.split(".")))
        self.version = version_string


if __name__ == "__main__":
    """Compares versions between the current and old.

    Args:
        version1 (arg 1) (str): old version number (x.y.z)
        operator (arg 2) (str): current version number (x.y.x)
        version2 (arg 3) (str): file to check version in
    Raises:
        VersionError: if the compared values don't match
    """
    if len(sys.argv) != 4:
        print("Usage: python script.py <version1> <operator> <version2>")
        sys.exit(1)

    version1 = sys.argv[1]
    operator_str = sys.argv[2]
    version2 = sys.argv[3]

    version1 = VersionObject(version1)
    version2 = VersionObject(version2)

    if operator_str in OPERATORS:
        if not OPERATORS[operator_str](version1.parsed, version2.parsed):
            raise VersionError(
                f"Version {version1.version} is not {operator_str} than "
                f"version {version2.version}"
            )
    else:
        raise ValueError(
            f"Invalid operator {operator_str}. Only gt, lt, eq are allowed."
        )
