# NSE institutional cash-activity fixtures

Captured from the public NSE endpoints on 8 October 2026, for session 8 October 2026.
These two small JSON payloads are unmodified source responses; tests run offline.

- [NSE-only](https://www.nseindia.com/api/fiidiiTradeNse)
- [Combined NSE/BSE/MSEI](https://www.nseindia.com/api/fiidiiTradeReact)
- [Report page](https://www.nseindia.com/reports/fii-dii)
- [Page script mapping each endpoint to its scope](https://www.nseindia.com/dist/js/sections/reports/fii-dii.js)
- [Column metadata defining amounts in INR crore](https://www.nseindia.com/json/reports/fii-dii.json)

The endpoints supply a trading date, not a publication timestamp. Production code
conservatively uses the observation time for point-in-time availability. Fixtures
use explicit synthetic observation timestamps; they do not establish when the
figures first became public. Exchange data is provisional; it is not the
custodian-confirmed NSDL series. These endpoints currently provide the latest
session only. The collector must not pretend they provide historical backfill.
