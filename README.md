# antnuptracker-server
Server backend for AntNupTracker. 

Copyright (C) 2020 Abouheif Lab

Visit us at https://www.antnuptialflights.com to learn more about our project. For the client app, see [this repository](https://github.com/bzrudski/antnuptracker-client). This application is a Django-based web app for recording, storing and accessing ant nuptial flight information. The web framework is written using Django, with a REST API added using Django REST Framework (to be documented...). Knox is used for authentication. This app should work on most major operating systems and should be compatible with the major database engines used by Django.

## Note on Licensing
This server-side application is licensed under the GNU AGPLv3 (see `COPYING`). However, there are a few trademarked-dependencies that cannot be licensed in this form. These include social networking and app-distribution related image files. As a result, these files have been excluded from the repository. In cases where such an icon would be used, please ensure that there is adequate alt text or a comment indicating what proprietary icon must be put there.

All files from Django Rest Framework are Copyright © 2011-present, Encode OSS Ltd.

The list of genera and species presented in the app (last updated summer of 2019) is found at `nuptialtracker/nuptiallog/taxonomyRaw` and was copied from [Category:Extant species](https://antwiki.org/wiki/Category:Extant_species) on _AntWiki_. In keeping with the original licensing, this list is licensed under the [Creative Commons Attribution-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-sa/4.0/).

Weather information from [OpenWeatherMap](https://openweathermap.org/), which is made available here under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/).

The website is typeset in [Dosis](https://fonts.google.com/specimen/Dosis) by Impallari Type and [Open Sans](https://fonts.google.com/specimen/Open+Sans) by Steve Matteson.

The `Terms and Conditions` and `Privacy Policy` were obtained from [TermsFeed](termsfeed.com/). The necessary templates have been omitted from the repository.

## Note on Contributions
* Do **not** push your changes to `settings.py` to this repo. This file is required for **you** to be able to run your modified web app on a development system. The production version uses its own `settings.py`.
* Do **not** push your changes to any environmental variable names unless they are necessary. Do **not** push your `.env` file to this repository.
* Do **not** add proprietary social media icons. Instead, put an `img` tag (if in `HTML`) with descriptive alternate text
* Always go through a pull request

## Documentation and Naming conventions
At the moment, very little of the code is documented. This will change soon.

In terms of naming conventions, there is a mix of `snake_case` and `camelCase` used in the code. This is due to the Django/Python prevalence of `snake_case` coming into conflict with my personal preference of `camelCase`. Ideally, both can coexist as long as we standardise which convention is used for which purposes.

The official name of this app is **AntNupTracker**. However, it was originally **NuptialLog** and then **NuptialTracker**. These names remain throughout the file hierarchy. Eventually, we may switch all references to **AntNupTracker**. If you want, do this in a pull request. Just make sure to fix **all** the imports.

## Note on `static`, `static_files` and `media`
* `media` is for user-uploaded flight images
* `static` contains the static files for the project
* `static_files` is the `STATIC_ROOT`

## Note on `curl`
A key feature of this server-side app is push notifications. To deliver push notifications to iOS devices, an `HTTP/2` connection must be established. This is beyond the capabilities of the `python-requests` module. Therefore, `pycurl` was initially used. However, the hosting environment for the production version of the site does not have `pycurl` installed with `nghttp2`, so a custom installation of `curl` was used. If you have `pycurl` installed in a way that allows you to make `HTTP/2` requests, feel free to uncomment the `pycurl`-related lines in `nuptialtracker/nuptiallog/notifications.py`. However, the official code will continue to rely on using `curl`.

## Note on Notifications
To be able to fully take advantage of the notification features described above, you must provide an iOS push notifications signing key. If you are not a member of the Apple Developer Program, simply comment out the lines in `nuptialtracker/nuptiallog/views.py` that create a new thread to send notifications.

## Note on Weather
All weather data stored on the server is obtained from <a href="https://openweathermap.org/">OpenWeatherMap</a>. This data is made available here under the <a href="https://opendatacommons.org/licenses/odbl/1-0/">Open Database License (ODbL)</a>. In order to be able to fetch and parse weather data, you must obtain an API Key from OpenWeatherMap (free option available). Otherwise, simply comment out the lines in `nuptialtracker/nuptiallog/views.py` that create a new thread to fetch the weather.

## Instructions for setting up a test server
In order to set up a test server, the following must be performed:

1. Clone this repository
    ```bash
    git clone https://github.com/bzrudski/antnuptracker-server.git
    ```
2. Set up the web server with the `WSGI` configuration
3. Install `curl` with `nghttp2` (required for `HTTP/2` support and `iOS` notifications)
4. Set up a `virtualenv` in the root directory of the repository: 
    ```bash
    $ virtualenv env
    $ source env/bin/activate
    $ pip install -r requirements.txt
    ```
5. Set up the following environment variables (use a `.env` file)
   ```bash
    export SECRET_KEY=''
    export DB_PASS=''
    export DB_USER=''
    export EMAIL_PASS=''
    export EMAIL_ADDR=''
    export KID=''
    export ISS=''
    export WEATHERKEY=''
    export TOKFILE=''
    export KEYPATH=''
    export CURLPATH=''
    export FAQPATH=''
    export TAXONOMY_FILE=''
    export APNS_TOPIC=''
   ```
    The variables `KID`, `ISS`, `TOKFILE`, `APNS_TOPIC` and `KEYPATH` are required for `iOS` notifications. The variable `WEATHERKEY` is obtained from `OpenWeather`.

   Make sure to edit the web server settings to pass these environment variables to the web server. In Apache, add the above declarations to `/etc/apache2/envvars`. If you need to rename any of the environmental variables, make sure to change them in relevant source files. MAKE SURE NOT TO COMMIT THESE CHANGES.
6. Edit `nuptialtracker/nuptialtracker/settings.py` to add your database and email settings. If your server does not have an `SSL` certificate, edit the security settings to prevent `HTTPS` redirect and to allow for insecure `CSRF` tokens. **You must configure your database before moving on to the next step.**
7. Install the `requirements` (you may want to create a virtual environment).
   ```bash
   $ pip install -r requirements.txt
   ```
   If any requirements are missing, please open an issue or submit a pull request.
8.  Perform the database migrations
    ```bash
    $ python manage.py migrate
    ```

9. Restart the web server
10. In order to report flights, the taxonomy database must be rebuilt. In order to do this, enter the Django shell. Make sure to run your `.env` file first to load the `SECRET_KEY`.
    ```bash
    $ python manage.py shell
    ```
    ```python
    > from nuptiallog import taxonomy
    > taxonomy.create_Genus_Objects(taxonomy.GENERA)
    > taxonomy.create_Species_Objects(taxonomy.SPECIES)
    ```

Now, your development server will work. Remember that if you want to test the mobile app with your modified server app, you must change the `baseURL` in the `URLManager.swift` file of the app's source code (see [this repository](https://github.com/bzrudski/antnuptracker-client)).

IOS is a trademark or registered trademark of Cisco in the U.S. and other countries. Apple and App Store are trademarks of Apple Inc., registered in the U.S. and other countries.