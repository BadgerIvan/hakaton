---
source: pdf/installation_b2664a854c94.pdf
source_format: pdf
title: installation
category: documentation
vendor: ЦФТ
date_parsed: '2026-11-21'
chunk_strategy: hierarchical
sha256: 8b85ea9e7c46907c171e8948858bd6805db62456f4be694053cf98236d25c9f7
pages: 24
source_url: https://catalog.cft.ru/6c29793a140a811d0c45ce03c1c93a28/document/%D0%94%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D1%8F%2C%20%D1%81%D0%BE%D0%B4%D0%B5%D1%80%D0%B6%D0%B0%D1%89%D0%B0%D1%8F%20%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D1%8E%20%D0%B4%D0%BB%D1%8F%20%D1%83%D1%81%D1%82%D0%B0%D0%BD%D0%BE%D0%B2%D0%BA%D0%B8%20%D0%B8%20%D1%8D%D0%BA%D1%81%D0%BF%D0%BB%D1%83%D0%B0%D1%82%D0%B0%D1%86%D0%B8%D0%B8%20%D0%BF%D1%80%D0%BE%D0%B3%D1%80%D0%B0%D0%BC%D0%BC%D0%BD%D0%BE%D0%B3%D0%BE%20%D0%BE%D0%B1%D0%B5%D1%81%D0%BF%D0%B5%D1%87%D0%B5%D0%BD%D0%B8%D1%8F.zip
language: ru
---

# installation

## Страница 1

Установка ЦФТ-Среда разработки
Документация администратора
28/10/2024

## Страница 2

Оглавление
Установка ЦФТ-Среда разработки. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 1
Online установка . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 2
Offline установка из зеркала в Nexus Repository Manager 3 OSS . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 3
Создание зеркала Nexus . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 3
Подготовка инсталлятора . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 8
Offline установка из файлового зеркала . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 10
Создание файлового зеркала . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 10
Подготовка инсталлятора . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 10
Offline установка из http-сервера. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 12
Настройка http-сервера . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 12
Подготовка репозиториев для зеркалирования ЦФТ-Среда разработки. . . . . . . . . . . . . . . . . . . . . . 16
Подготовка инсталлятора . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 17
Подготовка схемы к работе ЦФТ-Среда разработки . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 19
Обновление ТЯ . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 19
Конфигурирование схемы (не актуально для версии ТЯ 7.6.7.0 и выше) . . . . . . . . . . . . . . . . . . . . . 19
Настройка сервиса Database Change Notification . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 19
Обновление на новую версию . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 20
Обновление зеркал сайтов обновлений. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 20
Обновление модулей на существующих инсталляциях . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 20
Откат на предыдущую версию . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 20

## Страница 3

Установка ЦФТ-Среда разработки
Установка и обновление ЦФТ-Среда разработки выполняется с использованием сайтов обновлений,
представляющих собой хранилища модулей, используемых приложением.
Доступны три варианта установки и обновления ЦФТ-Среда разработки:
• Online установка/обновление. Сайт обновлений находится на сервере ЦФТ. Необходимо
наличие доступа в Интернет с рабочего места пользователя в процессе первоначальной
установки и последующего обновления ранее установленного продукта. См. Online установка.
• Offline установка/обновление из зеркала в Nexus Repository Manager 3 OSS. Сайт
обновлений располагается на Nexus сервере во внутренней сети организации. Доступ в
Интернет с рабочего места пользователя не требуется. См. Offline установка из зеркала в Nexus
Repository Manager 3 OSS.
• Offline установка/обновление из файлового зеркала в локальной сети. Сайт обновлений
располагается во внутренней сети организации. Доступ в Интернет с рабочего места
пользователя не требуется. См. Offline установка из файлового зеркала.
• Offline установка/обновление из http-сервера. Сайт обновлений располагается на http-
сервере во внутренней сети организации. Доступ в Интернет с рабочего места пользователя не
требуется. См. Offline установка из http-сервера.
1

## Страница 4

Online установка
Сохранить локально файл https://nexus.cft.ru/ide/cft-platform-ide-inst.zip. И распаковать архив.
По-умолчанию, инсталлятор работает в режиме online установки. В данном режиме создание
зеркала не требуется, установка будет выполняться непосредственно с сайта обновлений ЦФТ. Для
работы обновления необходимо обеспечить доступ в Интернет со всех рабочих мест пользователей.
Cписок репозиториев, которые должны быть доступны при установке:
• https://nexus.cft.ru/ide/latest/setups
• https://nexus.cft.ru/ide/latest/repository
• https://nexus.cft.ru/ide/latest/dbi-repository
• https://nexus.cft.ru/ide/latest/updatesites
• https://nexus.cft.ru/ide/previous/setups
• https://nexus.cft.ru/ide/previous/repository
• https://nexus.cft.ru/ide/previous/dbi-repository
• https://nexus.cft.ru/ide/previous/updatesites
Никакой дополнительной настройки инсталлятора не требуется.
 Возможностьописана в разделеоткатаОткатна предыдущуюна предыдущуюверсиюверсию.инсталляции ЦФТ-Среда разработки
2

## Страница 5

Offline установка из зеркала в Nexus
Repository Manager 3 OSS
В данном режиме установка и обновление будет происходить с сайта обновлений, расположенного
на сервере Nexus Repository Manager 3 OSS (далее Nexus) во внутренней сети организации. Доступ
в Интернет с рабочего места пользователя не требуется.
Nexus позволяет создать локальную копию сайтов обновлений ЦФТ. При выпуске новой версии ЦФТ-
Среда разработки, она будет автоматически скачена при первой попытке обновления. Последующие
обновления до новой версии будут происходить с локальной копии, сохраненной на Nexus сервере.
Данная версия является свободно распространяемым ПО. Скачать его можно по ссылке:
https://www.sonatype.com/nexus-repository-oss.
Официальная документация доступна по ссылке: https://help.sonatype.com/repomanager3.
Как работает Nexus:
• При обращении к Nexus с любого рабочего места, на котором запущено обновление ЦФТ-Среда
разработки, происходит проверка наличия нужной версии плагина в зеркале репозитория.
• Если нужная версия найдена в зеркале, то она возвращается в ответе на запрос.
• Если нужная версия не найдена в зеркале, то Nexus обратится за ней на сайт сопровождения.
• Если на сайте сопровождения нужная версия найдена, то она сохраняется в зеркало и
возвращается в ответе на запрос.
• Если на сайте сопровождения нужная версия не найдена, то возникнет ошибка обновления.
 Работоспособностьнаписания документации:решения3.64.0-04.подтверждена на версии, актуальной на момент
Создание зеркала Nexus
Первоначальная настройка Nexus
1. Скачать и установить дистрибутив Nexus.
2. Запустить Nexus командой nexus /run из папки <nexus_dir>/bin
3. Залогиниться под учетной записью администратора (admin).
4. После успешного логина, сменить пароль на надежный.
5. Переходим в режим администрирования сервера. На панели в верху страницы нажимаем кнопку
[ "Server administration and configuration" ].
6. Переходим в раздел [ Repositories ]
7. По-умолчанию, в нем уже настроены некоторые общедоступные maven и nuget репозитории. Они
нам не потребуются. Их можно или удалить или перевести в offline режим.
3

## Страница 6

8. Создаем один maven2-proxy репозиторий и шесть p2-proxy репозиториев по инструкции ниже:
Создание maven2-proxy репозитория для зеркалирования конфигурации
установки
1. В разделе [ Repositories ] нажимаем кнопку [ Create repository ].
2. Выбираем тип репозитория [ maven2 (proxy) ].
3. Вводим [ Name ]. Например, ru.cft.platform.ide.setup.latest
4. Вводим [ URL ] https://nexus.cft.ru/ide/latest/setups
5. Взводим checkbox [ Use certificates stored in the Nexus truststore to connect to external
systems ]
6. По кнопке [ View certificate ] открывается окно с информацией о сертификате сайта
https://nexus.cft.ru.
7. Нажать на кнопку [ Add certificate to truststore ]
4

## Страница 7

8. Устанавливаем Maximum component age = 0
9. Устанавливаем Maximum metadata age = 0
5

## Страница 8

Создание p2-proxy репозитория для зеркалирования updatesite с
обновлениями ЦФТ-Среда разработки
1. В разделе [ Repositories ] нажимаем кнопку [ Create repository ].
2. Выбираем тип репозитория [ p2 (proxy) ].
3. Вводим [ Name ]. Например, ru.cft.platform.ide.updatesite.latest
4. Вводим [ URL ] https://nexus.cft.ru/ide/latest/repository
6

## Страница 9

5. По аналогии создаем репозиторий для зеркалирования updatesite с предыдущей версией
модулей ЦФТ-Среда разработки:
a. Вводим [ Name ]. Например, ru.cft.platform.ide.updatesite.previous
b. Вводим [ URL ] https://nexus.cft.ru/ide/previous/repository
Создание p2-proxy репозитория для зеркалирования updatesite с
обновлениями dbi-компонент ЦФТ-Среда разработки
1. В разделе [ Repositories ] нажимаем кнопку [ Create repository ].
2. Выбираем тип репозитория [ p2 (proxy) ].
3. Вводим [ Name ]. Например, ru.cft.platform.ide.dbi.updatesite.latest
4. Вводим [ URL ] https://nexus.cft.ru/ide/latest/dbi-repository
5. По аналогии создаем репозиторий для зеркалирования updatesite с предыдущей версией dbi-
компонент ЦФТ-Среда разработки:
a. Вводим [ Name ]. Например, ru.cft.platform.ide.dbi.updatesite.previous
b. Вводим [ URL ] https://nexus.cft.ru/ide/previous/dbi-repository
Создание p2-proxy репозитория для зеркалирования updatesite со
сторонними зависимостями
1. В разделе [ Repositories ] нажимаем кнопку [ Create repository ].
2. Выбираем тип репозитория [ p2 (proxy) ].
3. Вводим [ Name ]. Например, ru.cft.platform.ide.externals.updatesite.latest
4. Вводим [ URL ] https://nexus.cft.ru/ide/latest/updatesites
7

## Страница 10

5. По аналогии создаем репозиторий для зеркалирования updatesite с предыдущей версией
сторонних зависимостей:
a. Вводим [ Name ]. Например, ru.cft.platform.ide.externals.updatesite.previous
b. Вводим [ URL ] https://nexus.cft.ru/ide/previous/updatesites
 Возможностьописана в разделеоткатаОткатна предыдущуюна предыдущуюверсиюверсию.инсталляции ЦФТ-Среда разработки
Подготовка инсталлятора
Сохранить локально файл https://nexus.cft.ru/ide/cft-platform-ide-inst.zip. И распаковать архив.
В том же каталоге, рядом с исполняемым файлом инсталлятора, создать конфигурационный файл
cft-platform-ide-inst.ini.
Файл cft-platform-ide-inst.ini можно создать автоматически с помощью утилиты
 [ ru.cft.platform.setup.customizer.jar ].https://nexus.cft.ru/ide/latest/setups.zip в Даннаяпапке утилитаresources.поставляетсяДля запускав модуляархиве
утилиты требуется наличие на рабочей станции Java версии 8 или выше.
Содержимое конфигурационного файла должно быть следующим:
-Doomph.installer.update.url=http://nexus_server/repository/latest/ru.cft.platform.ide
.externals.updatesite/
-Doomph.redirection.setups=index:/
->jar:http://nexus_server/repository/latest/ru.cft.platform.ide.setup/ru/cft/platform/
ru.cft.platform.ide.setup/1.0.1/ru.cft.platform.ide.setup-1.0.1.jar!/
-Doomph.setup.ecf.read.timeout=60000
-Doomph.update.url=http://nexus_server/repository/latest/ru.cft.platform.ide.externals
.updatesite/
-Dru.cft.platform.ide.externals.updatesite=http://nexus_server/repository/latest/ru.cf
t.platform.ide.externals.updatesite/
-Dru.cft.platform.ide.updatesite=http://nexus_server/repository/latest/ru.cft.platform
.ide.updatesite/
-Dru.cft.platform.ide.dbi.updatesite=http://nexus_server/repository/latest/ru.cft.plat
form.ide.dbi.updatesite/
В файле cft-platform-ide-inst.ini должно быть 7 строк, начинающихся с -D.
 Каждаяпредставленынастройкана 2-3 должнастроках из-занаходитьсяограниченияна однойразмерастроке.страницыВышедокументации.настройки
Ни в одной строке не должно быть перевода строки!
где nexus_server - url сервера Nexus Repository Manager 3 OSS (созданный на шаге Создание
зеркала Nexus). Например, nexus.cft.ru.
8

## Страница 11

Пример cft-platform-ide-inst.ini:
-Doomph.installer.update.url=http://localhost:8081/repository/latest/ru.cft.platform.i
de.externals.updatesite/
-Doomph.redirection.setup=index:/
->jar:http://localhost:8081/repository/latest/ru.cft.platform.ide.setup/ru/cft/platfor
m/ru.cft.platform.ide.setup/1.0.1/ru.cft.platform.ide.setup-1.0.1.jar!/
-Doomph.setup.ecf.read.timeout=60000
-Doomph.update.url=http://localhost:8081/repository/latest/ru.cft.platform.ide.externa
ls.updatesite/
-Dru.cft.platform.ide.externals.updatesite=http://localhost:8081/repository/latest/ru.
cft.platform.ide.externals.updatesite/
-Dru.cft.platform.ide.updatesite=http://localhost:8081/repository/latest/ru.cft.platfo
rm.ide.updatesite/
-Dru.cft.platform.ide.dbi.updatesite=http://localhost:8081/repository/latest/ru.cft.pl
atform.ide.updatesite/
После этого инсталлятор готов для установки на рабочих местах пользователей.
 Еслинеобходимоперед установкойкопировать дистрибутивоба файла (exeбудети ini)!скопирован на локальный компьютер, то
9

## Страница 12

Offline установка из файлового зеркала
В данном режиме установка и обновление будет происходить с сайта обновлений ЦФТ-Среда
разработки, расположенного локальной сети организации. Доступ в Интернет с рабочего места
пользователя не требуется.
Необходимо предоставить доступ к сетевой папке offline-зеркала со всех рабочих мест
пользователей.
Первичная настройка и последующее периодическое обновление offline-зеркала выполняется
вручную сотрудником организации.
Для обновления offline-зеркала достаточно повторить шаги, описанные в разделе Создание
файлового зеркала. Повторной настройки инсталлятора и/или конфигурации не требуется.
Создание файлового зеркала
Для создания файлового offline-зеркала с последней версией ЦФТ-Среда разработки необходимо
распаковать архивы с сайтами обновления в специальный общий каталог, который должен быть
доступен с каждого рабочего места пользователя.
• сайт обновлений ЦФТ-Среда разработки распаковать в папку latest\repository:
https://nexus.cft.ru/ide/latest/repository.zip
• сайт обновлений dbi-компонент ЦФТ-Среда разработки распаковать в папку latest\dbi-
repository: https://nexus.cft.ru/ide/latest/dbi-repository.zip
• сайт обновлений зависимостей (сторонних компонент, обязательных для работы ЦФТ-Среда
разработки) распаковать в папку latest\updatesites: https://nexus.cft.ru/ide/latest/updatesites.zip
• конфигурация инсталлятора распаковать в папку latest\setups: https://nexus.cft.ru/ide/latest/
setups.zip
Для создания файлового offline-зеркала с предыдущей версией ЦФТ-Среда разработки необходимо
распаковать архивы с сайтами обновления в специальный общий каталог, который должен быть
доступен с каждого рабочего места пользователя.
• сайт обновлений ЦФТ-Среда разработки распаковать в папку previous\repository:
https://nexus.cft.ru/ide/previous/repository.zip
• сайт обновлений dbi-компонент ЦФТ-Среда разработки распаковать в папку previous\dbi-
repository: https://nexus.cft.ru/ide/previous/dbi-repository.zip
• сайт обновлений зависимостей (сторонних компонент, обязательных для работы ЦФТ-Среда
разработки) распаковать в папку previous\updatesites: https://nexus.cft.ru/ide/previous/
updatesites.zip
• конфигурация инсталлятора распаковать в папку previous\setups: https://nexus.cft.ru/ide/previous/
setups.zip
 ВозможностьОткат на предыдущуюотката наверсию.предыдущую версию инсталляции IDE описана в разделе
Подготовка инсталлятора
Сохранить локально файл https://nexus.cft.ru/ide/cft-platform-ide-inst.zip. И распаковать архив.
В том же каталоге, рядом с исполняемым файлов инсталлятора, создать конфигурационный файл
cft-platform-ide-inst.ini.
10

## Страница 13

Файл cft-platform-ide-inst.ini можно создать автоматически с помощью утилиты
 [ ru.cft.platform.setup.customizer.jar ].https://nexus.cft.ru/ide/latest/setups.zip в Даннаяпапке утилитаresources.поставляетсяДля запускав модуляархиве
утилиты требуется наличие на рабочей станции Java версии 8 или выше.
Содержимое конфигурационного файла должно быть следующим:
-Doomph.installer.update.url=file:////comp/latest/updatesites/
-Doomph.redirection.setups=index:/
->jar:file:////comp/latest/setups/ru/cft/platform/ru.cft.platform.ide.setup/1.0.1/ru.c
ft.platform.ide.setup-1.0.1.jar!/
-Doomph.setup.ecf.read.timeout=60000
-Doomph.update.url=file:////comp/latest/updatesites/
-Dru.cft.platform.ide.externals.updatesite=file:////comp/latest/updatesites/
-Dru.cft.platform.ide.updatesite=file:////comp/latest/repository/
-Dru.cft.platform.ide.dbi.updatesite=file:////comp/latest/dbi-repository/
где ЦФТ-Среда разработки
• comp/latest/setups/ - полный путь к каталогу с конфигурацией
• comp/latest/updatesites/ - полный путь к зеркалу сайтов обновлений зависимостей
• comp/latest/repository/ - полный путь к зеркалу сайтов обновлений ЦФТ-Среда разработки
• comp/latest/dbi-repository/ - полный путь к зеркалу сайтов обновлений dbi-компонент ЦФТ-Среда
разработки
 Путьсимволомне должен«/». содержать символов кирилицы. Путь должен заканчиваться
Настройка -Doomph.redirection.setups должна находиться на одной строке. Выше
настройка представлена на двух строках из-за ограничения размера страницы 
документации. Перевода строки в ней быть не должно!
После этого инсталлятор готов для установки на рабочих местах пользователей.
 Еслинеобходимоперед установкойкопировать дистрибутивоба файла (exeбудети ini)!скопирован на локальный компьютер, то
В итоге должна получиться подобная структура:
11

## Страница 14

Offline установка из http-сервера
В данном режиме установка и обновление будет происходить с сайта обновлений, расположенного
на файловом http-сервере во внутренней сети организации. Доступ в Интернет с рабочего места
пользователя не требуется.
Необходимо предоставить доступ к http-серверу со всех рабочих мест пользователей.
В качестве http-сервера можно использовать любой сервер, поддерживающий раздачу файлов.
Например, Microsoft IIS или nginx.
Первичная настройка и последующее периодическое обновление файлов, раздаваемых http-
сервером, выполняется вручную сотрудником организации. При выпуске новой версии ЦФТ-Среда
разработки, архивы с сайтами обновления ЦФТ вручную переносятся в специальные общие
каталоги http-сервера и в последующем становятся доступными для скачивания пользователями.
Настройка http-сервера
Настройка http-сервера nginx
Установку и настройку nginx выполните согласно руководству https://nginx.org/ru/docs/
beginners_guide.html#static
Создайте структуру каталогов, из которых будут раздаваться файлы зеркал ЦФТ-Среда разработки.
Например:
root/data
ide
latest
dbi-repository
repository
setups
updatesites
previous
dbi-repository
repository
setups
updatesites
Далее выполните пункт Подготовка репозиториев для зеркалирования ЦФТ-Среда разработки
Настройка http-сервера IIS
1. Зайдите на сервер с правами администратора. Запустите Server Manager и в панели Dashboard
выберите пункт [ Add roles and features ].
12

## Страница 15

2. На странице выбора ролей сервера отметьте [ Web Server (IIS) ].
3. В последующих пунктах выберите нужные роли и компоненты или оставьте по умолчанию.
4. Если требуется настроить авторизацию по паролю, включите и выполните настройку Basic
Authentication.
13

## Страница 16

5. Выберите пункт меню [ Tools ] и запустите [ Internet Information Services (IIS) Manager ].
6. Сразу после установки IIS по умолчанию создаётся пустой сайт [ Default Web Site ]. Создайте на
диске root папку для хранение файлов IIS сервера. (По умолчанию создаётся папка
c:/inetpub/wwwroot). В root папке создайте следующую иерархию папок:
14

## Страница 17

<root папка>
ide
latest
dbi-repository
repository
setups
updatesites
previous
dbi-repository
repository
setups
updatesites
В эти папки в дальнейшем будут сохраняться файлы зеркала ЦФТ-Среда разработки.
Сконфигурируйте root директорию для ограничения прав и разрешения скачивания файлов. Все
необходимые настройки доступа к каталогам и привязки сайта выполните на основной странице
диспетчера служб.
В root папке создайте файл web.config. Cодержание файла:
15

## Страница 18

<?xml version="1.0" encoding="UTF-8"?>
<configuration>
<system.webServer>
<security>
<authorization>
<!-- Deny all users access to the root of the website, since it
contains this web.config -->
<remove users="*" roles="" verbs="" />
<add accessType="Deny" users="*" />
</authorization>
</security>
<staticContent>
<mimeMap fileExtension=".*" mimeType="application/octet-stream" />
</staticContent>
<defaultDocument enabled="false" />
</system.webServer>
<location path="ide" allowOverride="false">
<system.webServer>
<directoryBrowse enabled="true" showFlags="Date, Time, Size, Extension" />
<security>
<authorization>
<!-- Allow all users access to the ide folder -->
<remove users="*" roles="" verbs="" />
<add accessType="Allow" users="*" roles="" />
</authorization>
</security>
</system.webServer>
</location>
</configuration>
7. Перезапустите IIS сервер.
Далее выполните пункт Подготовка репозиториев для зеркалирования ЦФТ-Среда разработки.
Подготовка репозиториев для зеркалирования ЦФТ-
Среда разработки
1. Скачать с сайта сопровождения архивы с последней версией ЦФТ-Среда разработки:
◦https://nexus.cft.ru/ide/latest/setups.zip
◦https://nexus.cft.ru/ide/latest/repository.zip
◦https://nexus.cft.ru/ide/latest/dbi-repository.zip
◦https://nexus.cft.ru/ide/latest/updatesites.zip
2. Распаковать архивы в настроенные соответствующие директории http-сервера:
◦setups → server_root_dir/ide/latest/setups
◦repository → server_root_dir/ide/latest/repository
◦dbi-repository → server_root_dir/ide/latest/dbi-repository
16

## Страница 19

◦updatesites → server_root_dir/ide/latest/updatesites
3. Скачать с сайта сопровождения архивы с предыдущей версией ЦФТ-Среда разработки:
◦https://nexus.cft.ru/ide/previous/setups.zip
◦https://nexus.cft.ru/ide/previous/repository.zip
◦https://nexus.cft.ru/ide/previous/dbi-repository.zip
◦https://nexus.cft.ru/ide/previous/updatesites.zip
4. Распаковать архивы в настроенные соответствующие директории http-сервера:
◦setups → server_root_dir/ide/previous/setups
◦repository → server_root_dir/ide/previous/repository
◦dbi-repository → server_root_dir/ide/previous/dbi-repository
◦updatesites → server_root_dir/ide/previous/updatesites
где server_root_dir - root-директория http-сервера, настроенная на шаге Настройка http-сервера
 Возможностьописана в разделеоткатаОткатна предыдущуюна предыдущуюверсиюверсию.инсталляции ЦФТ-Среда разработки
Подготовка инсталлятора
Сохранить локально файл https://nexus.cft.ru/ide/cft-platform-ide-inst.zip. И распаковать архив.
В том же каталоге, рядом с исполняемым файлов инсталлятора, создать конфигурационный файл
cft-platform-ide-inst.ini.
Файл cft-platform-ide-inst.ini можно создать автоматически с помощью утилиты
 [ ru.cft.platform.setup.customizer.jar ].https://nexus.cft.ru/ide/latest/setups.zip в Даннаяпапке утилитаresources.поставляетсяДля запускав модуляархиве
утилиты требуется наличие на рабочей станции Java версии 8 или выше.
Содержимое конфигурационного файла должно быть следующим:
-Doomph.installer.update.url=http://http_server/latest/updatesites/
-Doomph.redirection.setups=index:/
->jar:http://http_server/latest/setups/ru/cft/platform/ru.cft.platform.ide.setup/1.0.1
/ru.cft.platform.ide.setup-1.0.1.jar!/
-Doomph.setup.ecf.read.timeout=60000
-Doomph.update.url=http://http_server/latest/updatesites/
-Dru.cft.platform.ide.externals.updatesite=http://http_server/latest/updatesites/
-Dru.cft.platform.ide.updatesite=http://http_server/latest/repository/
-Dru.cft.platform.ide.dbi.updatesite=http://http_server/latest/dbi-repository/
где http_server - url http-сервера, созданного на шаге Настройка http-сервера.
17

## Страница 20

Пример cft-platform-ide-inst.ini:
-Doomph.installer.update.url=http://server.bank.ru/latest/updatesites/
-Doomph.redirection.setups=index:/
->jar:http://server.bank.ru/latest/setups/ru/cft/platform/ru.cft.platform.ide.setup/1.
0.1/ru.cft.platform.ide.setup-1.0.1.jar!/
-Doomph.setup.ecf.read.timeout=60000
-Doomph.update.url=http://server.bank.ru/latest/updatesites/
-Dru.cft.platform.ide.externals.updatesite=http://server.bank.ru/latest/updatesites/
-Dru.cft.platform.ide.updatesite=http://server.bank.ru/latest/repository/
-Dru.cft.platform.ide.dbi.updatesite=http://server.bank.ru/latest/dbi-repository/
Настройка -Doomph.redirection.setups должна находиться на одной строке. Выше
настройка представлена на трех строках из-за ограничения размера страницы 
документации. Перевода строки в ней быть не должно!
После этого инсталлятор готов для установки на рабочих местах пользователей.
 Еслинеобходимоперед установкойкопировать дистрибутивоба файла (exeбудети ini)!скопирован на локальный компьютер, то
18

## Страница 21

Подготовка схемы к работе ЦФТ-Среда
разработки
Обновление ТЯ
Обновить ТЯ до версии 7.6.7.1 или выше.
Конфигурирование схемы (не актуально для версии
ТЯ 7.6.7.0 и выше)
В системных параметрах на схеме необходимо установить размер пула соединений с помощью
настройки IDE.MAX_CONNECTIONS. Рекомендуемое значение 10.
 ЕслиIDE.MAX_CONNECTIONSна схеме установленазаполнится автоматически.версия ТЯ 7.6.7.0 и выше, то настройка
Настройка сервиса Database Change Notification
Данный сервис используется для получения уведомлений из БД о блокировках и актуальности
операций. Для работы данного сервиса необходимо открытие порта 47632 на клиентской машине со
стороны сервера БД.
Сервис Database Change Notification не работает на pluggable database.

19

## Страница 22

Обновление на новую версию
Новость о выходе новой версии ЦФТ-Среда разработки публикуются на сайте сопровождения:
https://support.cft.ru/systems/platform_ide/news/news
При выпуске обновлений для перехода на новую версию необходимо выполнить следующие
действия:
• Обновление зеркал сайтов обновлений. Только для offline установки из файлового зеркала.
• Обновление модулей на существующих инсталляциях. По-умолчанию, ЦФТ-Среда разработки
автоматически предлагает установить новые версии модулей при их обнаружении.
Обновление зеркал сайтов обновлений
1. При использовании в качестве источника установки файлового зеркала, требуется периодически
обновлять зеркала вручную. Для этого необходимо скачать новые архивы и заменить
содержимое соответствующего общего каталога (см. Создание файлового зеркала).
2. При использовании в качестве источника установки http-сервера также требуется периодически
обновлять содержимое каталогов сервера вручную. Для этого необходимо скачать новые архивы
и заменить содержимое соответствующих каталогов сервера (см. Подготовка репозиториев для
зеркалирования ЦФТ-Среда разработки).
 Притребуется.online установке или использовании зеркала Nexus, обновление зеркал не
Обновление модулей на существующих инсталляциях
После запуска ЦФТ-Среда разработки обычно запускается автоматическое обновление в
соответствии с текущей конфигурацией. О запуске автообновления говорит появление значка в
нижнем правом углу АРМа.
В случае если обновление не запускается автоматически, можно вызвать его принудительно с
помощью команды Cправка › Perfom Setup Tasks….
После установки обновлений необходимо перезапустить ЦФТ-Среда разработки. 
Откат на предыдущую версию
Иногда бывают ситуации, при которых нет возможности продолжать работу на последней версии
ЦФТ-Среда разработки. Например, ЦФТ-Среда разработки требует новой версии патча серверного
API. А установить его нет возможности или сроки установки не известны. Или в новой версии
обнаруживается дефект, отсутствующий в предыдущей версии.
Откат возможен только на одну версию назад. 
Конфигурация репозиториев
Чтобы иметь возможность оперативного отката ЦФТ-Среда разработки на предыдующую версию
необходимо в инсталляции ЦФТ-Среда разработки однократно указать три urlа. Они будут
использоваться для поиска предыдующих версий модулей ЦФТ-Среда разработки.
Для этого нужно открыть окно Oкно › Параметры… › Установка/обновление › Доступные сайты
20

## Страница 23

обновлений:
С помощью кнопки [ Добавить ] добавить три Url на предыдущую версию модулей ЦФТ-Среда
разработки и сторонних зависимостей.
При online установке это:
• https://nexus.cft.ru/ide/previous/repository
• https://nexus.cft.ru/ide/previous/dbi-repository
• https://nexus.cft.ru/ide/previous/updatesites
При offline установке с использованием в качестве источника установки:
• Nexus Repository Manager. Необходимо указать пути до репозиториев, созданных на этапе
Создание зеркала Nexus.
• Файлового зеркала. Необходимо указать пути до репозиториев, созданных на этапе Создание
файлового зеркала.
• Http-сервера. Необходимо указать пути до репозиториев, созданных на этапе Подготовка
репозиториев для зеркалирования ЦФТ-Среда разработки.
Процедура отката
Для отката на предыдущую версию ЦФТ-Среда разработки необходимо последовательно выполнить
шаги:
• Открыть окно Cправка › О программе ЦФТ-Среда разработки › Детали установки › История
установки;
• В списке истории установок выбрать пункт, следующий за [ Текущая установка ];
• Нажать на кнопку [ Восстановить ].
• После окончания отката перезапустить ЦФТ-Среда разработки.
21

## Страница 24

22
