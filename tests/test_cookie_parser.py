#!/usr/bin/env python3

from tweet_fetcher.extractors.auth_playwright.auth import TwitterAuth

# Example cookie table
cookie_table = """__cf_bm	wi3p9oT6gFeEEck8lmbipjRfjnrUAG.snJjLVe2Gh_Q-1742644161-1.0.1.1-td7L1nyE1XryhHweENqd9UEoI3fwRhpc38sL3rJozb7ypz4nrTsUs2S05ZxLU7ALfv6rbDtfNnlqcXKa8p8G_U242dgfiIkYCFjS6BTe8u8	.x.com	/	2025-03-22T12:19:21.946Z	177	✓	✓	None			Medium	
auth_multi	"136618804:755a6669542eb0cb257839435447015b65b5ad9a|811128179884781568:ac7ab9a86798794ad5e0cdd4258bf9cdf78b503b"	.x.com	/	2026-04-22T10:52:25.699Z	122	✓	✓	Lax			Medium	
auth_token	a1f73b6cc7fefbd4466df9a4d651740c100bda65	.x.com	/	2026-04-22T10:11:12.855Z	50	✓	✓	None			Medium	
ct0	4a6dffb4c9220de970a2d15c760de0ad95198863f09e61690c3701898bf9c6414437935d5cd9132d2256f80ca03e1dd819b804e3bcef0dfd3925f6fabbcc1ddc93a039e5679d739afd488f0c179607b4	.x.com	/	2026-04-22T10:11:13.306Z	163		✓	Lax			Medium	
d_prefs	MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw	.x.com	/	2025-07-09T14:39:48.194Z	59		✓				Medium	
dnt	1	.x.com	/	2026-04-22T10:11:12.855Z	4		✓	None			Medium	
guest_id	v1%3A174263821673474799	.twitter.com	/	2026-04-26T10:10:17.023Z	31		✓	None			Medium	
guest_id	v1%3A174263827279062459	.x.com	/	2026-04-22T10:11:13.306Z	31		✓	None			Medium	
guest_id_ads	v1%3A174224186544469054	.twitter.com	/	2026-04-21T20:04:24.811Z	35		✓	None			Medium	
guest_id_ads	v1%3A169549221149633047	.x.com	/	2026-02-10T14:39:48.651Z	35		✓	None			Medium	
guest_id_marketing	v1%3A174224186544469054	.twitter.com	/	2026-04-21T20:04:24.811Z	41		✓	None			Medium	
guest_id_marketing	v1%3A169549221149633047	.x.com	/	2026-02-10T14:39:48.651Z	41		✓	None			Medium	
kdt	SjKe4XI7Zdlsl4R4iRX5KgG8KGLD78jNpBW04OwZ	.x.com	/	2026-04-22T10:11:12.855Z	43	✓	✓				Medium	
lang	en	x.com	/	Session	6						Medium	
personalization_id	"v1_0T0QSTka1kLapeR2HhYJTg=="	.twitter.com	/	2026-04-21T20:04:24.811Z	47		✓	None			Medium	
personalization_id	"v1_0T0QSTka1kLapeR2HhYJTg=="	.x.com	/	2026-03-17T20:04:28.481Z	47		✓	None			Medium	
twid	u%3D1306736056985948162	.twitter.com	/	2026-04-26T10:52:24.796Z	27		✓	None			Medium	
twid	u%3D1306736056985948162	.x.com	/	2026-03-22T10:52:28.894Z	27		✓	None			Medium"""

# Create auth manager and parse cookie table
auth = TwitterAuth(cookies=None, cookie_table=cookie_table)

# Print simplified cookies (backward compatible)
print('Simplified cookies (prioritizing .x.com):')
for name, value in auth.cookies.items():
    print(f'{name}: {value[:30]}...' if len(value) > 30 else f'{name}: {value}')

print(f'\nTotal simplified cookies: {len(auth.cookies)}')

# Print full cookie data with domains
print('\nFull cookie data (with domains):')
cookie_count = 0
for name, cookies in auth.cookie_data.items():
    for i, cookie_info in enumerate(cookies):
        domain = cookie_info['domain']
        value = cookie_info['value']
        cookie_count += 1
        print(f'{name} [{domain}]: {value[:30]}...' if len(value) > 30 else f'{name} [{domain}]: {value}')

print(f'\nTotal cookies with domains: {cookie_count}') 