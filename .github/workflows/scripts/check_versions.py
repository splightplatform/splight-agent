import sys

from pkg_resources import parse_version as parse


class VersionError(Exception):
    """Raised when the new version is not greater than the old version."""


import sys

from pkg_resources import parse_version as parse


class VersionError(Exception):
    """Raised when the new version is not greater than the old version."""


if __name__ == "__main__":
    """Compares versions between the current and old.

    Args:
        old_version (arg 1) (str): old version number (x.y.z)
        new_version (arg 2) (str): current version number (x.y.x)
        file_name (arg 3) (str): file to check version in
    Raises:
        VersionError: if the current version is not greater than old version
    """
    old_version_line = sys.argv[1]
    new_version_line = sys.argv[2]
    file_name = sys.argv[3]

    old_version = parse(old_version_line)
    current_version = parse(new_version_line)

    if current_version <= old_version:
        raise VersionError(
            f"New version {current_version} is not greater than "
            f"old version {old_version} in file {file_name}"
        )


if __name__ == "__main__":
    """Compares versions between the current and old.

    Args:
        old_version (arg 1) (str): old version number (x.y.z)
        new_version (arg 2) (str): current version number (x.y.x)
    Raises:
        VersionError: if the current version is not greater than old version
    """
    old_version_line = sys.argv[1]
    new_version_line = sys.argv[2]

    old_version = parse(old_version_line)
    current_version = parse(new_version_line)

    if current_version <= old_version:
        raise VersionError(
            f"New version {current_version} is not greater than "
            f"old version {old_version}"
        )
