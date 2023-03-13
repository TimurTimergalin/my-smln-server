db.createUser(
    {
        user: "admin",
        pwd: "admin",
        roles: [
            {
                role: "readWrite",
                db: "db"
            }
        ]
    }
)

db = db.getSiblingDB("smln-server")

db.users.createIndex(
    {
        "login": 1
    },
    {
        "unique": true
    }
);

db.files.createIndex(
    {
        "token": 1
    },
    {
        "unique": true
    }
);

db.chats.createIndex(
    {
        "users": 1
    }
)
db.test_collection.insertOne({"test": "test"})
db.test_collection.drop()