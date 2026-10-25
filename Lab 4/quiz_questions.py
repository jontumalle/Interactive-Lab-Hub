"""Question bank for the utensil quiz.

The screen asks:  "What utensil should you use for <dish>?"
The right answer is the exact set of utensils to pick up (names match fork_sensor.UTENSILS).
`why` is a short line to show after answering.
"""

PROMPT = "What utensil should you use for {dish}?"

QUESTIONS = [
    # --- one utensil -------------------------------------------------------
    {"dish": "a side salad", "answer": {"fork"}, "why": "Leafy salads are eaten with a fork."},
    {"dish": "a slice of birthday cake", "answer": {"fork"}, "why": "Cake is a fork job."},
    {"dish": "scrambled eggs", "answer": {"fork"}, "why": "Scoop and stab with a fork."},
    {"dish": "tomato soup", "answer": {"spoon"}, "why": "Soup is a spoon job."},
    {"dish": "a bowl of cereal", "answer": {"spoon"}, "why": "Milk and cereal need a spoon."},
    {"dish": "a scoop of ice cream", "answer": {"spoon"}, "why": "Spoon it up before it melts."},
    {"dish": "a bowl of chili", "answer": {"spoon"}, "why": "Thick and soupy: spoon."},
    {"dish": "butter on a bread roll", "answer": {"knife"}, "why": "Spread it with a knife."},
    {"dish": "jam on toast", "answer": {"knife"}, "why": "Spreading is a knife job."},
    {"dish": "a block of cheese on a cheese board", "answer": {"knife"}, "why": "Cut a slice with the knife."},
    # --- two utensils ------------------------------------------------------
    {"dish": "a steak", "answer": {"fork", "knife"}, "why": "Knife to cut, fork to hold and eat."},
    {"dish": "a stack of pancakes", "answer": {"fork", "knife"}, "why": "Cut the stack, then eat with the fork."},
    {"dish": "a grilled chicken breast", "answer": {"fork", "knife"}, "why": "Cut it with the knife, eat with the fork."},
    {"dish": "pad thai", "answer": {"fork", "spoon"}, "why": "In Thai dining the fork pushes food onto the spoon."},
    {"dish": "apple pie a la mode", "answer": {"fork", "spoon"}, "why": "Fork for the pie, spoon for the ice cream."},
    {"dish": "a soft-boiled egg", "answer": {"knife", "spoon"}, "why": "Slice the top off, then scoop it out."},
    # --- all three ---------------------------------------------------------
    {"dish": "a dinner of soup, then steak, then ice cream", "answer": {"fork", "knife", "spoon"},
     "why": "Soup and ice cream: spoon. Steak: fork and knife."},
]
