# Reduced control/score reference: supplied mod e8s1.rpy:3148,3153,3314,3320.
# Nested scene labels are lifted to top level for the independent fixture runner.
default tori = 0
default valerie = 0
default mod_toriVal_nips = False
label start:
    menu:
        "Mod: Both":
            $ mod_toriVal_nips = True
            jump mod_tori
label mod_tori:
    $ tori += 1
    $ toriNip = True
    $ persistent.toriNip = True
    "Tori branch"
    if mod_toriVal_nips:
        jump mod_val
    jump shared_end
label mod_val:
    $ valerie += 1
    $ valNip = True
    $ persistent.valNip = True
    "Valerie branch"
    jump shared_end
label shared_end:
    "Shared continuation"
    return
