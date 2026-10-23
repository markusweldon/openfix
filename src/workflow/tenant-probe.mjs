// Trusted reference probe. Target code runs only after explicit --execute.
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { writeFile } from 'node:fs/promises';
try {
  const module = await import(pathToFileURL(path.join(process.argv[2], 'src/invoices.mjs')).href);
  if (typeof module.lookupInvoice !== 'function') throw new Error('Expected lookupInvoice(user, id, invoices) export');
  const invoices = [{ id:'invoice-a', tenantId:'tenant-a', amount:120 }, { id:'invoice-b', tenantId:'tenant-b', amount:240 }];
  let own, cross, ownError, crossError;
  try { own = await module.lookupInvoice({ tenantId:'tenant-a' },'invoice-a',structuredClone(invoices)); } catch (e) { ownError = String(e.message); }
  try { cross = await module.lookupInvoice({ tenantId:'tenant-b' },'invoice-a',structuredClone(invoices)); } catch (e) { crossError = String(e.message); }
  const legitimate = own?.id === 'invoice-a' && own?.tenantId === 'tenant-a' && own?.amount === 120;
  const leaked = cross?.id === 'invoice-a' && cross?.tenantId === 'tenant-a';
  const blocked = cross == null && (!crossError || /forbidden|not found|unauthorized/i.test(crossError));
  await writeFile(process.argv[3],JSON.stringify({ profile:'tenant-isolation', legitimate, leaked, blocked,
    observations:{ ownInvoice:own?.id || null, crossTenantInvoice:cross?.id || null, ownError, crossError } }),{flag:'wx',mode:0o600});
} catch (error) { console.error(error.message); process.exitCode = 2; }
