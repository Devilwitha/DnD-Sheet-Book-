[app]
title = DnD Lokal
package.name = dndlocal
package.domain = ch.bollisoft
source.dir = .
source.include_exts = py,png,jpg,kv,db,json,txt,ttf
source.exclude_dirs = tests,scripts,recipes,.github,.git,.venv,venv,.delegate,.local-tools,.test-output,.pytest_cache,build,dist,bin,__pycache__
source.exclude_patterns = requirements*.txt
version.regex = ^([0-9]+\.[0-9]+\.[0-9]+)
version.filename = %(source.dir)s/version.txt
requirements = python3,kivy==2.3.1,pyjnius,android,zeroconf==0.147.0,ifaddr==0.2.0,psutil==7.0.0,sqlite3,segno==1.6.6,Pillow==9.5.0,reportlab,charset-normalizer
icon.filename = %(source.dir)s/logo/logo.png
presplash.filename = %(source.dir)s/logo/logo.png
orientation = portrait,landscape,portrait-reverse,landscape-reverse
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE,CAMERA
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.accept_sdk_license = True
android.add_src = android_src
android.add_activities = ch.bollisoft.dndlocal.scan.QrScanActivity
android.gradle_dependencies = com.google.zxing:core:3.5.4
android.add_compile_options = "sourceCompatibility = 1.8", "targetCompatibility = 1.8"
android.manifest.orientation = sensor
android.archs = arm64-v8a
android.allow_backup = False
p4a.branch = v2024.01.21
p4a.bootstrap = sdl2
p4a.local_recipes = recipes

[buildozer]
log_level = 2
warn_on_root = 1
