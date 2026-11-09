# Sentetik oyun 5 — takma ad (alias) grubu senaryosu:
# Ayni secim ayni karakterin iki takma adini birlikte artirir
# (love_luna ve luna_points). min_alias_cooccur esigiyle bu ikisi
# ayni karakter grubuna dusmeli; hedef-karakter modunda puan toplami
# eksik kalmamali.

define luna = Character('Luna')
define maya = Character('Maya')
default love_luna = 0
default luna_points = 0
default love_maya = 0
default maya_favor = 0

label start:
    "Bolum 1 basliyor."
    menu:
        "Luna'ya gonderme yap":
            $ love_luna += 1
            $ luna_points += 1
            jump b2
        "Maya'ya gonderme yap":
            $ love_maya += 1
            $ maya_favor += 1
            jump b2

label b2:
    "Gun 2."
    menu:
        "Luna ile sahneye cik":
            $ love_luna += 1
            $ luna_points += 1
            luna "Guzeldi."
            jump b3
        "Maya ile sahneye cik":
            $ love_maya += 1
            $ maya_favor += 1
            maya "Guzeldi."
            jump b3

label b3:
    "Gun 3."
    menu:
        "Luna'ya gonderme yap":
            $ love_luna += 1
            $ luna_points += 1
            jump final
        "Maya'ya gonderme yap":
            $ love_maya += 1
            $ maya_favor += 1
            jump final

label final:
    "Son bolum."
    return

label ending_death:
    "Hayatta kalamadin."
    $ renpy.quit()
