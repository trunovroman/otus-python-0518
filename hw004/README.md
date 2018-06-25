# API скоринга
Обрабатывает POST запросы. Выдает информацию по скорингу (см. примеры ниже). Для работы скрипта требуется Python 3.

## Запуск HTTP-сервера
Для запуска сервера необходимо из директории со скриптом выполнить команду:
```
$ python3 api.py [--log LOG_FILE_PATH] [--port PORT]
```
где:\
`LOG_FILE_PATH` — путь до файла лога. По умолчанию лог пишется в stdout.\
`PORT` — порт, на котором будет запущен HTTP-сервер. По умолчанию 8080.

## Примеры запросов с кодом ответа 200 (OK)
Пример вызова метода clients_interests: 

```
$ curl -X POST -H "Content-Type: application/json" -d '{"account": "horns&hoofs", "login": "user23", "method": "clients_interests", "token": "8195bd0d4773708c1940410eb838a0bf3b88b9a03d09eba0403741b8a63f7f1a7e0c874be378c297d6332a9f3929c4e2d1524d90d675e6b83cba01372cac2e22", "arguments": {"client_ids": [1,2,3,4], "date": "20.07.2017"}}' http://127.0.0.1:8080/method/
```
Ответ:
 ```
{"response": {"1": ["music", "travel"], "2": ["pets", "travel"], "3": ["music", "cinema"], "4": ["otus", "geek"]}, "code": 200}
 ```
 
Пример вызова метода online_score:
```
$ curl -X POST -H "Content-Type: application/json" -d '{"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95", "arguments": {"phone": "79175002040", "email": "stupnikov@otus.ru", "first_name": "Стансилав", "last_name": "Ступников", "birthday": "01.01.1990", "gender": 1}}' http://127.0.0.1:8080/method/

```
Ответ:
```
{"response": {"score": 5.0}, "code": 200}
```

## Примеры запросов с кодом ответа 422 (INVALID_REQUEST)
При вызове метода clients_interests передается параметр date равный 120.07.2017, что является ошибкой: 

```
$ curl -X POST -H "Content-Type: application/json" -d '{"account": "horns&hoofs", "login": "user23", "method": "clients_interests", "token": "8195bd0d4773708c1940410eb838a0bf3b88b9a03d09eba0403741b8a63f7f1a7e0c874be378c297d6332a9f3929c4e2d1524d90d675e6b83cba01372cac2e22", "arguments": {"client_ids": [1,2,3,4], "date": "120.07.2017"}}' http://127.0.0.1:8080/method/
```
Ответ:
```
{"error": ["Field: date. time data '120.07.2017' does not match format '%d.%m.%Y'"], "code": 422}
```
 
При вызове метода online_score для параметра gender указывается значение 6, которое является недопустимым:
```
$ curl -X POST -H "Content-Type: application/json" -d '{"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95", "arguments": {"phone": "79175002040", "email": "stupnikov@otus.ru", "first_name": "Стансилав", "last_name": "Ступников", "birthday": "01.01.1990", "gender": 6}}' http://127.0.0.1:8080/method/
```
Ответ:
```
{"error": ["Field: gender. Gender must be equal to [0, 1, 2]"], "code": 422}
```

## Примеры запросов с кодом ответа 403 (FORBIDDEN)
При вызове метода clients_interests указывается неверный token: 

```
$ curl -X POST -H "Content-Type: application/json" -d '{"account": "horns&hoofs", "login": "user23", "method": "clients_interests", "token": "8195bd0d4773708c1940410eb838a0bf3b88b9a03d09eba0403741b8a63f7f1a7e0c874be378c297d6332a9f392975e6b83cba01372cac2e22", "arguments": {"client_ids": [1,2,3,4], "date": "20.07.2017"}}' http://127.0.0.1:8080/method/
```
Ответ:
```
{"error": "Forbidden", "code": 403}
```
 
При вызове метода online_score передается неверный token:
```
$ curl -X POST -H "Content-Type: application/json" -d '{"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34ebcd5a08f21fc95", "arguments": {"phone": "79175002040", "email": "stupnikov@otus.ru", "first_name": "Стансилав", "last_name": "Ступников", "birthday": "01.01.1990", "gender": 1}}' http://127.0.0.1:8080/method/

```
Ответ:
 ```
{"error": "Forbidden", "code": 403}
 ```
## Пример запроса с кодом ответа 400 (BAD_REQUEST)
При вызове метода clients_interests передается неверный json (пропущена запятая после параметра `account`: 

```
$ curl -X POST -H "Content-Type: application/json" -d '{"account": "horns&hoofs" "login": "user23", "method": "clients_interests", "token": "8195bd0d4773708c1940410eb838a0bf3b88b9a03d09eba0403741b8a63f7f1a7e0c874be378c297d6332a9f392975e6b83cba01372cac2e22", "arguments": {"client_ids": [1,2,3,4], "date": "20.07.2017"}}' http://127.0.0.1:8080/method/
```
Ответ:
```
{"error": "Bad Request", "code": 400}
```
## Пример запроса с кодом ответа 404 (NOT_FOUND)
При вызове метода clients_interests указывается неверный адрес `http://127.0.0.1:8080/unknown_method/`: 

```
$ curl -X POST -H "Content-Type: application/json" -d '{"account": "horns&hoofs", "login": "user23", "method": "clients_interests", "token": "8195bd0d4773708c1940410eb838a0bf3b88b9a03d09eba0403741b8a63f7f1a7e0c874be378c297d6332a9f392975e6b83cba01372cac2e22", "arguments": {"client_ids": [1,2,3,4], "date": "20.07.2017"}}' http://127.0.0.1:8080/test_method/
```
Ответ:
```
{"error": "Not Found", "code": 404}
```
## Запуск тестов
Тесты лежат в папке со скриптом. Тесты запускаются командой:
```
$ python3 -m unittest test.py
```
