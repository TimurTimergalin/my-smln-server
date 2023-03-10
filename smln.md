# Дополнения к протоколу SMLN

## Типы

### Дополнения к стандартным типам SMLN

#### user

```
{
    "id": <int>,
    "public-key": <str>
    "username": <string>,
    "role": <string>,
    "is-online": <bool>,
    "last-seen": <unixtime>
}
```

`"username"` и `"role"` только буквы, цифры и символы: пробел, дефис, нижнее подчеркивание.

#### message

```
{
    "sender": <int>,
    "receiver": <int>,
    "text": <string>,
    "time": <unixtime>,
    "seen": <bool>,
    "files":
    [
    	<server-file>,
    	...
    ]
}
```



## Запросы

### Новые запросы

#### people-with-messages

Запрос вида `"people-with-messages"` возвращает массив пользователей, с которыми пользователь уже общался (то есть, существует сообщение от пользователя в массиве к текущему пользователю или наоборот) и последнее сообщение в беседе с этими пользователями.

Поля `"filter"`, `"sort"`, и `"is_ascending"` в `"list-properties"` игнорируются - пользователи не фильтруются, они упорядочены по времени отправки последнего сообщения в беседе с текущим пользователем (по убыванию). 

Запрос:

```
{
    "type": "people-with-messages",
    "args":
    {
        "list-properties": <list-properties>,
    }
}
```

Ответ:

```
{
    "type": "people-with-messages",
    "status": <response-status>,
    "args":
    {
        "chats":
        [
        	{
        		"user": <user>,
        		"last-message": <server-message>
    		},
        	...
        ]
    }
}
```

#### read
\
Запрос типа `"read"` нужен, чтобы пометить сообщения от пользователя как прочитанные

Запрос:

```
{
    "type": "read",
    "args":
    {
        "user-id": <int>
    }
}
```

Ответ:

Возможные ошибки:

- Пользователя с таким идентификатором не существует - 2

### Дополнения к стандартным запросам SMLN

#### people

Возможные значения `"filter"`:

- `"online"` - в этом случае будут возвращены только подключенные пользователи.
- `"role={role}"` - в этом случае будут возвращены только пользователи с определенной ролью.
- `"name-startswith={prefix}"` - в этом случае будут возвращены только те пользователи, чей `"username"` начинается с `prefix.`

Фильтры можно комбинировать с помощью `&` (например, `"filter": "online&role=project manager"`). 

Возможные значения `"sort"`:

- `"last-seen"` - пользователи будут отсортированы сначала по статусу подключения (`online/offline`), а затем по времени их последнего выхода в сеть. `"is-ascending"` по умолчанию - `false`.
- `"username"` - пользователи будут отсортированы по `"username"` (лексикографически) - сортировка по умолчанию. `"is-ascending"` по умолчанию - `true`.
- `"role"` - пользователи будут отсортированы по роли `"role"` (лексикографически). `"is-ascending"` по умолчанию - `true`.

#### messages

Возможные значения `"filter"`:

- `"has-files"` - в этом случае будут возвращены только те сообщения, к которым приложены какие-либо файлы.
- `"new"` - в этом случае будут возвращены только те сообщения, которые пользователь еще не читал.

Значение поля `"sort"` игнорируется - сообщения сортируются по времени отправки.

Значение поля `"is-ascended"` игнорируется - сообщения сортируются по убыванию.

## События

### Новые события

#### activity-update

Событие типа `"activity-update"` отправляется всем подключенным пользователям, когда другой пользователь подключается к сети/отключается от сети.

```
{
    "type": "activity-update",
    "args":
    {
        "user-id": <int>,
        "is-online": <bool>,
        "last-seen": <unixtime>
    }
}
```

#### messages-read

Событие типа `"messages-read"` отправляется пользователю, чьи сообщения прочитал другой пользователь (поле `"user-id"`)

```
{
	"type": "messages-read",
	"args":
	{
		"user-id": <int>
	}
}
```

