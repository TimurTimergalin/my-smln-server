from db.mongo_db import MongoDB


all_drivers = ["MongoDB"]


def get(driver_name):
    if driver_name not in all_drivers:
        raise ValueError("Unknown driver")
    return globals()[driver_name]


if __name__ == '__main__':
    print(get("MongoDB"))
