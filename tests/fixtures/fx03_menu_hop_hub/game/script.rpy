# Sentetik oyun 3 — menu-hop / stop-label senaryosu:
# Secenekler ortak bir "hub" etiketine atlar; hub icinde ikinci bir menu var.
# follow_menu_hops=0 (varsayilan) tarama hub'da durur; 1+ ise hop sonrasindaki
# kiyafet/olum kanitlari da toplanir.

define luna = Character('Luna')
define maya = Character('Maya')
default love_luna = 0
default love_maya = 0

label start:
    "Hikaye burada baslar."
    menu:
        "Luna ile konus (+1 love_luna)":
            $ love_luna += 1
            jump choice_hub
        "Maya ile konus (+1 love_maya)":
            $ love_maya += 1
            jump choice_hub

label choice_hub:
    "Ortik bir alandasin."
    menu:
        "Calismaya devam et (+1 love_luna)":
            $ love_luna += 1
            jump after_hub
        "Yarismayi katil (+1 love_maya)":
            $ love_maya += 1
            jump after_hub

label after_hub:
    luna "Konustugumuz icin tesekkurler."
    $ love_luna += 2
    "Gun bitti."
    return

label ending_death:
    "Hayatta kalamadin."
    $ renpy.quit()
