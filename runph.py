import asyncio
from src.ph import main
import src.ph as ph
ph.onefile = True
asyncio.run(main.shell_loop())
def runph():
    ph.onefile = True
    asyncio.run(main.shell_loop())
if __name__ == '__main__':
    main()