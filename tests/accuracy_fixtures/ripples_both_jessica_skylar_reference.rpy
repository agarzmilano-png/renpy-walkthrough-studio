# Reduced control/score reference from supplied Ripples-0.9.22-Multi-Mod.
# e3s11.rpy:249,344; e5s1.rpy:7059,7120. Presentation shortened deliberately.
default skylar = 0
default skylarL = 0
default jessica = 0
default mod_skylar_jess = None
default skylarRisk = False
default jessicaRisk = False
label start:
    menu:
        "Mod: Both":
            $ mod_skylar_jess = True
            $ skylar += 1
            $ skylarL += 1
            $ jessica += 1
            $ relationshipSkylar = "More Than Friends"
            $ persistent.relationshipSkylar = "More Than Friends"
            $ skylarRisk = True
            $ persistent.skylarRisk = True
            jump e3s11choiceJess
label e3s11choiceJess:
    "Jessica branch"
    if mod_skylar_jess:
        jump e3s11choiceSky
    jump ep3sc12
label e3s11choiceSky:
    "Skylar branch"
    jump ep3sc12
label ep3sc12:
    if jessicaRisk or mod_skylar_jess:
        "Later Jessica branch"
    if skylarRisk:
        "Later Skylar branch"
    return
