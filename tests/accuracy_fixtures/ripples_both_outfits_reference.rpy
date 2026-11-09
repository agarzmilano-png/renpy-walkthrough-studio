# Reduced control/score reference: supplied mod e5s1.rpy:5043,5529.
default shelbyS = 0
default shelbyD = 0
default mod_shelby_outfits = False
label start:
    menu:
        "Mod: Both":
            $ mod_shelby_outfits = True
            $ shelbyPlayful = True
            $ persistent.shelbyPlayful = True
            $ shelbyS += 1
            $ shelbySexy = True
            $ persistent.shelbySexy = True
            $ shelbyD += 1
            jump e5s6Playful
label e5s6Playful:
    "Playful branch"
    if mod_shelby_outfits:
        jump e5s6Sexy
    jump shared_end
label e5s6Sexy:
    "Sexy branch"
    jump shared_end
label shared_end:
    "Shared continuation"
    return
