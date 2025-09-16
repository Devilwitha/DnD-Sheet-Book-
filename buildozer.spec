[app]
title = DnDApp
package.name = dndapp
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,db,json,txt,enemies,session,char
version = 0.1
requirements = python3,kivy,zeroconf
orientation = landscape
fullscreen = 1
android.accept_licenses = True
icon.filename = %(source.dir)s/logo/logo.png
presplash.filename = %(source.dir)s/osbackground/splash.png
android.permissions = INTERNET

[buildozer]
log_level = 2
warn_on_root = 1
