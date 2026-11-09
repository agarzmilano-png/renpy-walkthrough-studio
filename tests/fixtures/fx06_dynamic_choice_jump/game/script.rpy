# Sentetik oyun 6 — secenek govdesinde dinamik jump ifadesi:
# 'jump expression t' secenek govdesinde oldugu icin secenek dynamic_jump_unresolved
# alir; runtime probe 't' degiskeninin gozlenen degerini gostermek durumundadir.

define luna = Character('Luna')
default t = ""

label start:
    "Test basalsin."
    menu:
        "Kapilari kontrol et":
            if bosluk:
                $ t = "open_path"
            else:
                $ t = "closed_path"
            jump expression t

label open_path:
    luna "+1 love_luna"
    $ love_luna += 1
    return

label closed_path:
    "Kapali kaliyorsun."
    $ renpy.quit()
