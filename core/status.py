def status(code, mes=None):
    res = {"status": code}
    if mes is not None:
        res["error-message"] = mes

    return res


def ok():
    return status(0)


def server_error():
    return status(20, "Server error")


def invalid_format():
    return status(1, "Message is not a JSON object")


def unspecified_type():
    return status(1, 'Message does not contain "type" field')


def unknown_type(type_):
    return status(1, f'Unknown type: "{type_}"')


def absent_fields(fields):
    lst = ", ".join(f'"{x}"' for x in fields)
    return status(2, f'Following required fields are absent: {lst}')


def wrong_data_type(field):
    return status(2, f"Wrong data type of field: {field}")


def wrong_credentials():
    return status(4, "Authentication failed: wrong credentials")


def repeated_auth():
    return status(3, "Authentication was already made during the connection")


def auth_required():
    return status(3, "Authentication required to handle this request")


def invalid_list_properties(properties):
    lst = ", ".join(f'"{x}"' for x in properties)
    return status(2, f"Invalid values of list properties: {lst}")


def user_not_found(user_id):
    return status(2, f"No user with id: {user_id}")


def file_not_accessible(token):
    return status(3, f"Cannot access file: {token}")
