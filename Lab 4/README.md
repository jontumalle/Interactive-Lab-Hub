# Lab 4: Fine Dining Etiquette

## Team

- Jonathan Tumalle (jrt285)
- Ani Hadagali (ah2495)

## Part 1: Physical Interaction Design

### Design sketches

![Sketch 1](sketch1.png)

![Sketch 2](sketch2.png)

![Sketch 3](sketch3.png)

![Sketch 4](sketch4.png)

![Sketch 5](sketch5.png)

### Prototyping questions

Some questions came up include:

- If we went with the automatic dispenser idea, how would it dispense the utensils? How would we know it's strong enough to lift them up in a safe way?
	- For this we would need to simulate the dispensing. We could add weights to a platform the motor can push up and experiment to see what the limit is and compare it to the average weight of the most heavy utensil.
- For sketch 5, how would we know the motor can move to an angle that actually points to the correct object? Would we need a more precise motor than what we have available?
	- For this we could set up two utensils next to each other (a fork and a spoon) as they would in a regular table setting and see if we can utelize computer vision to determine there are 2 utensils.
- For using the sensors, how would we hide the connection to the sensors so that it isn't distracting from how it should be used?
	- We could prototype the system with just one fake paper utensil to see if we can hide the wiring.
- When we fix the number of utensils we allow the user to use, how do we know that we cover all the cases seen in the "fine dining" world?
	- This is not something physical prototyping can address since this is more of a hypothetical.
- How will the system determine whether a utensil has been placed in the correct position?
	- We could place capacitive sensors beneath designated table positions and test whether they can detect a utensil being placed or removed. We could try different sensor positions and materials between the sensor and utensil to determine how reliably the system detects placement.
- How will the system distinguish between different utensils placed in the same location?
	- We could test whether capacitive sensing can distinguish a fork from a spoon or whether we need separate designated placement zones. We could also experiment with identifying utensils through their shape or by attaching small markers, if appropriate.		
- How do we prevent the sensors from detecting a utensil that is near a position but not actually placed there?
	- We could move utensils around the edges of each sensing zone and test when the sensor activates. This would help us determine the appropriate size and spacing of each zone.
- How can we avoid forcing the user to constantly look between the phone and the table?
	- We could prototype alternative feedback methods, such as highlighting the next position on the phone while using a physical indicator or OLED at the table. We could then compare how easily users follow the instructions.
- How do we know the system has correctly detected the user's action?
	- We could test a series of known actions, such as picking up a fork, moving a spoon, or placing a knife down. We could compare the system's detected actions with what actually happened and record how often it makes mistakes.
- How long can the user wait between performing an action and receiving feedback?
	- We could measure the time between a sensor detecting an action and the display or servo responding. We could test different delays and observe whether the interaction feels immediate enough.

### Selected design

The user sits down at a simulated dining table. A screen displays a dish, such as soup, and asks the user to select the correct utensil. The user picks up a paper fork, knife, or spoon from the table setting. The system tells them whether their choice is correct and explains the appropriate etiquette.


I'd choose this design because it combines physical interaction, sensing, and feedback in a simple experience. It also lets you test the core idea before investing time in building the dispenser or integrating real sensors.

### Rough prototype

![IMG_6354](https://github.com/user-attachments/assets/ed944961-f9c0-4a53-a933-1c6b166d50a3)

## Part 2: Build & Integrate

### Working prototype: At the Table

The [phone viewer prototype](fine_dining/README.md) reads our capacitive cutlery sensor and gives live dining feedback. See its guide for starting/stopping the app, mapping utensils to channels, and editing scenarios.

From the repository root, run `"Lab 4/fine_dining/start.sh"` and open the printed URL on a phone on the same network. Stop with Ctrl+C.

### Iterations

[First prototype with fork video](https://drive.google.com/file/d/1KweES5yMQHb_wpn-slzBBrMNjegRI4kd/view?usp=share_link)
[Using phone for visuals](https://drive.google.com/file/d/1zc7f8b6v1P_vZ7R6gkTLNZFUfj7gj0DY/view?usp=share_link)
[Adding pictures and sound](https://drive.google.com/file/d/1Vb70O3qMolQDKml19VvHgUlTDk6Bypk4/view?usp=share_link)
