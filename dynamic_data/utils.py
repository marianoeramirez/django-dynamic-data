def in_exact_equal(value, array: tuple):
    for c in array:
        if type(c) == type(value) and c == value:
            return True
    return False


def parse_bool_value(value) -> int:
    if in_exact_equal(value, (True, 'True', 'true', 3, '3')):
        return 3
    elif in_exact_equal(value, (False, 'False', 'false', 2, '2')):
        return 2
    elif in_exact_equal(value, (None, '', 1, '1')):
        return 1
    else:
        return 0
