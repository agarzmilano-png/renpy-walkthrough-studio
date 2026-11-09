default gym = False
label start:
    menu:
        "Dalia ile spor salonuna git":
            $ gym = True
        "Evde kal":
            $ gym = False
    call check_route
    return
label check_route:
    if gym:
        jump dalia_entry
    return
label dalia_entry:
    "Dalia route"
    return
