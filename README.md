В кинопоиске нет такой функции как двойные субтитры, т.е чтобы были и английский и русские субтитры.
<br>
Для борьбы с пиратством используется DRM, поэтому видео можно смотреть только на сайте или в приложении. Взломать DRM очень сложно (и не легально :) )
WebOS - операционная система телевизоров LG. Отдельное приложения для webOS создать трудно. Поэтому, единственный выход - web-приложение, хотя и там тяжко на дефолтном (без альтернативы) браузере.
<br>
Ну вот, запускается сервер (server.py) на aiohttp за gunicorn'ом, пользователь заходит на локальный сайт, там логинится в kinopoisk. И далее наше приложение симулирует работу
сайта кинопоиска (отправляет запросы) и получается ссылки на stream'ы, какие-то штуки от DRM и все это отправляется библиотеке shaka, а shaka показывает видео.
<br>
Для запуска нужен Linux, gunicorn, python, в консоли: ```./start.sh```.
<br>
Сейчас приложение не работает, так как похоже что у Яндекса поменялась аутентификация. Раньше логинилось, запускало видео. Однако на webOS все равно нужно было допиливать (иногда видео не загружает или лагает).
<br>
Бесполезно, но интересно.
<br>
А еще я хотел сделать в этом проекте свой аналог React'а (зависть к фронтендерам).
<br>
А еще нужно настроить reverse proxy на nginx.
