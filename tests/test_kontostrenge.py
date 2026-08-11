"""Manuel live-test af kontostrenge.py."""

import logging
from datetime import date
from pprint import pprint

from q_prisme365_api.functionality.kontostrenge import (
    find_kontostreng_id,
    find_kontostreng_ids,
    get_driftsenhed,
    get_driftsenheder,
    parse_kontostreng,
    validate_kontostreng,
    validate_kontostrenge,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s: "
        "%(message)s"
    ),
)


# ------------------------------------------------------------
# VÆLG TEST
# ------------------------------------------------------------

TEST_PARSE = False
TEST_FIND_ONE_ID = False
TEST_FIND_MULTIPLE_IDS = False
TEST_GET_ONE_DRIFTSENHED = False
TEST_GET_MULTIPLE_DRIFTSENHEDER = False
TEST_GET_ALL_DRIFTSENHEDER = False
TEST_VALIDATE_ONE = True
TEST_VALIDATE_MULTIPLE = False


# ------------------------------------------------------------
# TESTDATA
# ------------------------------------------------------------

KONTOSTRENG_ONE = (
    "100201010000-645511002-10021-40-"
)

# Eksempel på en anden kontostreng:
# KONTOSTRENG_TWO = (
#     "180505020000-645511002-10021-40-"
# )

KONTOSTRENG_TWO = None


AFDELINGSNUMMER_ONE = "180505020000"

# Eksempel:
# AFDELINGSNUMMER_TWO = "100201010000"

AFDELINGSNUMMER_TWO = None


CONTROL_DATE = date.today()

ACCOUNT_STRUCTURE_NAME = "HAd"
BATCH_SIZE = 20


def main():
    """Kør de valgte live-tests."""

    if TEST_PARSE:
        test_parse()

    if TEST_FIND_ONE_ID:
        test_find_one_id()

    if TEST_FIND_MULTIPLE_IDS:
        test_find_multiple_ids()

    if TEST_GET_ONE_DRIFTSENHED:
        test_get_one_driftsenhed()

    if TEST_GET_MULTIPLE_DRIFTSENHEDER:
        test_get_multiple_driftsenheder()

    if TEST_GET_ALL_DRIFTSENHEDER:
        test_get_all_driftsenheder()

    if TEST_VALIDATE_ONE:
        test_validate_one()

    if TEST_VALIDATE_MULTIPLE:
        test_validate_multiple()


def test_parse():
    """Opdel én kontostreng lokalt."""

    result = parse_kontostreng(
        KONTOSTRENG_ONE
    )

    print()
    print("OPDELING AF KONTOSTRENG")
    pprint(result)


def test_find_one_id():
    """Find id for én kontostreng."""

    result = find_kontostreng_id(
        kontostreng=KONTOSTRENG_ONE,
        account_structure_name=(
            ACCOUNT_STRUCTURE_NAME
        ),
    )

    print()
    print("KONTOSTRENG-ID")
    pprint(result)


def test_find_multiple_ids():
    """Find id'er for flere kontostrenge."""

    results = find_kontostreng_ids(
        kontostrenge=build_account_list(),
        account_structure_name=(
            ACCOUNT_STRUCTURE_NAME
        ),
        batch_size=BATCH_SIZE,
    )

    print()
    print("KONTOSTRENG-ID'ER")
    pprint(results)


def test_get_one_driftsenhed():
    """Hent én driftsenhed."""

    result = get_driftsenhed(
        afdelingsnummer=(
            AFDELINGSNUMMER_ONE
        )
    )

    print()
    print("DRIFTSENHED")
    pprint(result)


def test_get_multiple_driftsenheder():
    """Hent flere driftsenheder samlet."""

    results = get_driftsenheder(
        afdelingsnumre=(
            build_department_list()
        ),
        batch_size=BATCH_SIZE,
    )

    print()
    print("DRIFTSENHEDER")
    pprint(results)


def test_get_all_driftsenheder():
    """Hent alle driftsenheder."""

    results = get_driftsenheder(
        afdelingsnumre=None,
        batch_size=BATCH_SIZE,
    )

    print()
    print("ANTAL DRIFTSENHEDER")
    print(len(results))

    print()
    pprint(results)


def test_validate_one():
    """Validér én kontostreng."""

    result = validate_kontostreng(
        kontostreng=KONTOSTRENG_ONE,
        dato=CONTROL_DATE,
    )

    print()
    print("VALIDERING AF KONTOSTRENG")
    pprint(result)


def test_validate_multiple():
    """Validér flere kontostrenge samlet."""

    results = validate_kontostrenge(
        kontostrenge=build_account_list(),
        dato=CONTROL_DATE,
        batch_size=BATCH_SIZE,
    )

    print()
    print("VALIDERING AF KONTOSTRENGE")
    pprint(results)


def build_account_list():
    """Byg listen med kontostrenge."""

    values = [
        KONTOSTRENG_ONE,
        KONTOSTRENG_TWO,
    ]

    results = []

    for value in values:
        if value:
            results.append(value)

    return results


def build_department_list():
    """Byg listen med afdelingsnumre."""

    values = [
        AFDELINGSNUMMER_ONE,
        AFDELINGSNUMMER_TWO,
    ]

    results = []

    for value in values:
        if value:
            results.append(value)

    return results


if __name__ == "__main__":
    main()