import sys, asyncio
sys.path.insert(0, __import__('os').path.dirname(__file__))
from cdp import Session
async def main():
    async with Session(sys.argv[1]) as s:
        await s.open(layout=int(sys.argv[2]) if len(sys.argv) > 2 else None)
        print('stat', await s.js("document.getElementById('stat').textContent"), 'rows', await s.js("lay.prims.length+'/'+lay.mprims.length"))
        print('layer rows', await s.js("document.querySelectorAll('#ltable .lrow').length"))
        print('errors', s.errors)
asyncio.run(main())
