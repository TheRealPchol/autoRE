import os
import keyboard
def shell():
    print('Pchol AutoRE System Shell')
    while True:
        try:
            if keyboard.is_pressed('f10'):
                break
            how = input('>>>')
            if how == "LICENSE":
                print('The license Pchol AutoRE is GNU GPL v3')
            else:
                os.system(how)
                if keyboard.is_pressed('f10'):
                    break
        except KeyboardInterrupt:
            print()
            break
