# Sentetik oyun 4 — dinamik jump ifadesi: jump expression degiskenle yapilir.
# Statik analiz bunu dynamic_jump_unresolved olarak isaretlemeli; hedef asagida
# iki aday etiket olarak mevcut (luna_path / maya_path).

define luna = Character('Luna')
define maya = Character('Maya')
default romance_target = "luna"
default love_luna = 0
default love_maya = 0

label start:
    "Romantik hedefini seçtiginde kod ona atlar."
    menu:
        "Yunus kafesini ac":
            $ love_luna += 1
            $ romance_target = "luna"
            jump dynamic_hub

label dynamic_hub:
    $ next_scene = romance_target + "_path"
    jump expression next_scene

label luna_path:
    luna "Benimle buradasin. (+1 love_luna)"
    $ love_luna += 1
    return

label maya_path:
    maya "Ben de buradayim (+1 love_maya)"
    $ love_maya += 1
    return

label ending_death:
    "Hayatta kalamadin."
    $ renpy.quit()
