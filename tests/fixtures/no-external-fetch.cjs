// Server tests must fail before any external API request can leave this process.
globalThis.fetch = () => { process.stderr.write('Unexpected external API request\n'); process.exit(86); };
