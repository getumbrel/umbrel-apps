const fs = require('fs/promises');
const path = require('path');

async function readAndPrint() {
  console.clear();
  console.log('\n ~~~');
  console.log('~ ~ ~  BASSIN');
  console.log(' ~~~\n');

  await readAndPrintPool(path.join(__dirname, '../www/pool', 'pool.status'));
  await readAndPrintUsers(path.join(__dirname, '../www', 'users'));
}

async function readAndPrintPool(file) {
  try {
    const content = await fs.readFile(file, 'utf-8');
    const lines = content.trim().split('\n').filter(Boolean);
    if (lines.length < 3) throw new Error('pool.status file is incomplete');

    const [pool, hashrate, shares] = lines.map(JSON.parse);

    const columns = [
      addColumnLines('hashrate', {
        '5m': hashrate.hashrate5m,
        '1h': hashrate.hashrate1hr,
        '1d': hashrate.hashrate1d,
        '7d': hashrate.hashrate7d,
      }, 0, 4),
      addColumnLines('shares', {
        'best': abbreviateNumber(shares.bestshare),
        'total': abbreviateNumber(shares.accepted),
        'reject': abbreviateNumber(shares.rejected),
        '/sec': shares.SPS5m,
      }, 6, 10),
      addColumnLines('pool', {
        'uptime': secondsToDHM(pool.runtime),
        'update': diffToNow(pool.lastupdate),
        'time': new Date().toLocaleString(),
        'users': `${pool.Users} / ${pool.Workers}`,
      })
    ];

    printColumns(columns);
    console.log('');
  } catch (error) {
    console.error('Error reading pool file:', error.message);
    process.exit(1);
  }
}

async function readAndPrintUsers(folder) {
  try {
    const folderPath = path.resolve(folder);
    const entries = await fs.readdir(folderPath);

    for (const user of entries) {
      const entryPath = path.join(folderPath, user);
      const stats = await fs.lstat(entryPath);

      if (!stats.isFile() || path.extname(user)) continue;

      try {
        const json = JSON.parse(await fs.readFile(entryPath, 'utf-8'));

        const columns = [
          addColumnLines('hashrate', {
            '5m': json.hashrate5m,
            '1h': json.hashrate1hr,
            '1d': json.hashrate1d,
            '7d': json.hashrate7d,
          }, 0, 4),
          addColumnLines('shares', {
            'best': abbreviateNumber(json.bestshare),
            'ever': abbreviateNumber(json.bestever),
            'total': abbreviateNumber(json.shares),
            'update': diffToNow(json.lastshare),
          }, 6, 10),
          addColumnLines('user', user),
        ];
  
        printColumns(columns);

        console.log('');
  
        for (const worker of json.worker || []) {
          const columns = [
            addColumnLines('hashrate', {
              '5m': worker.hashrate5m,
              '1h': worker.hashrate1hr,
              '1d': worker.hashrate1d,
              '7d': worker.hashrate7d,
            }, 0, 4),
            addColumnLines('shares', {
              'best': abbreviateNumber(worker.bestshare),
              'ever': abbreviateNumber(worker.bestever),
              'total': abbreviateNumber(worker.shares),
              'update': diffToNow(worker.lastshare),
            }, 6, 10),
            addColumnLines('worker', 
              worker.workername.replace(user, '').replace('.', '')
            ),
          ];
  
          printColumns(columns);

          console.log('');
        }

      } catch (error) {
        console.error('Error reading user file:', error.message);
        process.exit(1);
      }
    }
  } catch (error) {
    console.error('Error reading users directory:', error.message);
    process.exit(1);
  }
}

const printColumns = (columns) => {
  const maxRowsWorker = Math.max(...columns.map(t => t.length));
  
  for (let i = 0; i < maxRowsWorker; i++) {
    console.log(columns.map(t => t[i] || '').join(' '.padEnd(5)));
  }
}

const addColumnLines = (title, obj, minKeyWidth = 0, minValWidth = 0) => {
  const lines = [];
  const entries = Object.entries(obj);
  const keyWidth = Math.max(minKeyWidth, ...entries.map(([k]) => k.length)) + 1;
  const valWidth = Math.max(minValWidth, ...entries.map(([, v]) => String(v).length));

  lines.push(`${title.padEnd(keyWidth + valWidth + 1)}`);
  lines.push(`${'--'.padEnd(keyWidth + valWidth + 1)}`);

  if (typeof obj === 'string') {
    lines.push(obj);
  } else {
    for (const [key, value] of entries) {
      lines.push(`${key.padEnd(keyWidth)} ${String(value).padEnd(valWidth)}`);
    }
  }

  return lines;
}

const secondsToDHM = (s) => {
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const minutes = Math.floor((s % 3600) / 60);

  if (days > 0) {
      return `${days}d ${hours}h`;
  } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
  } else {
      return `${minutes}m`;
  }
}

const diffToNow = (timestamp) => {
  const diffFormatted = secondsToDHM(Math.floor(Date.now() / 1000) - timestamp);
  
  return diffFormatted === '0m' ? 'now' : `${diffFormatted} ago`;
}

const abbreviateNumber = (num) => {
  if (num >= 1e12) return (num / 1e12).toFixed(2) + 'T';
  if (num >= 1e9) return (num / 1e9).toFixed(2) + 'G';
  if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
  if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';

  return num.toString();
}

readAndPrint();
setInterval(readAndPrint, 60 * 1000);
