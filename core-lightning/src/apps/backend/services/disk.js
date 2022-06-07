/**
 * Generic disk functions.
 */

const logger = require("utils/logger");
const fs = require("fs");
const crypto = require("crypto");
const uint32Bytes = 4;

// Deletes a file from the filesystem
function deleteFile(filePath) {
  return new Promise((resolve, reject) =>
    fs.unlink(filePath, (err, str) => {
      if (err) {
        reject(err);
      } else {
        resolve(str);
      }
    })
  );
}

// Delete all items in a directory.
async function deleteItemsInDir(path) {
  const contents = fs.readdirSync(path);

  for (const item of contents) {
    const curPath = path + "/" + item;
    if (fs.statSync(curPath).isDirectory()) {
      deleteFolderRecursive(curPath);
    } else {
      fs.unlinkSync(curPath);
    }
  }
}

async function deleteFoldersInDir(path) {
  const contents = fs.readdirSync(path);

  for (const item of contents) {
    if (fs.statSync(path + "/" + item).isDirectory()) {
      deleteFolderRecursive(path + "/" + item);
    }
  }
}

function deleteFolderRecursive(path) {
  if (fs.existsSync(path)) {
    const contents = fs.readdirSync(path);

    for (const file of contents) {
      const curPath = path + "/" + file;
      if (fs.statSync(curPath).isDirectory()) {
        deleteFolderRecursive(curPath);
      } else {
        fs.unlinkSync(curPath);
      }
    }
    fs.rmdirSync(path);
  }
}

async function listDirsInDir(dir) {
  const contents = fs.readdirSync(dir);

  const dirs = [];

  for (const item of contents) {
    if (fs.statSync(dir + "/" + item).isDirectory()) {
      dirs.push(item);
    }
  }

  return dirs;
}

// Reads a file. Wraps fs.readFile into a native promise
function readFile(filePath, encoding) {
  return new Promise((resolve, reject) =>
    fs.readFile(filePath, encoding, (err, str) => {
      if (err) {
        reject(err);
      } else {
        resolve(str);
      }
    })
  );
}

// Reads a file as a utf8 string. Wraps fs.readFile into a native promise
async function readUtf8File(filePath) {
  return (await readFile(filePath, "utf8")).trim();
}

async function readJsonFile(filePath) {
  return readUtf8File(filePath).then(JSON.parse);
}

// Writes a string to a file. Wraps fs.writeFile into a native promise
// This is _not_ concurrency safe, so don't export it without making it like writeJsonFile
function writeFile(filePath, data, encoding) {
  return new Promise((resolve, reject) =>
    fs.writeFile(filePath, data, encoding, (err) => {
      if (err) {
        reject(err);
      } else {
        resolve();
      }
    })
  );
}

function writeJsonFile(filePath, obj) {
  const tempFileName = `${filePath}.${crypto
    .randomBytes(uint32Bytes)
    .readUInt32LE(0)}`;

  return writeFile(tempFileName, JSON.stringify(obj, null, 2), "utf8")
    .then(
      () =>
        new Promise((resolve, reject) =>
          fs.rename(tempFileName, filePath, (err) => {
            if (err) {
              reject(err);
            } else {
              resolve();
            }
          })
        )
    )
    .catch((err) => {
      if (err) {
        fs.unlink(tempFileName, (err) => {
          logger.warn("Error removing temporary file after error", "disk", {
            err,
            tempFileName,
          });
        });
      }
      throw err;
    });
}

function writeKeyFile(filePath, obj) {
  const tempFileName = `${filePath}.${crypto
    .randomBytes(uint32Bytes)
    .readUInt32LE(0)}`;

  return writeFile(tempFileName, obj, "utf8")
    .then(
      () =>
        new Promise((resolve, reject) =>
          fs.rename(tempFileName, filePath, (err) => {
            if (err) {
              reject(err);
            } else {
              resolve();
            }
          })
        )
    )
    .catch((err) => {
      if (err) {
        fs.unlink(tempFileName, (err) => {
          logger.warn("Error removing temporary file after error", "disk", {
            err,
            tempFileName,
          });
        });
      }
      throw err;
    });
}

module.exports = {
  deleteItemsInDir,
  deleteFile,
  deleteFoldersInDir,
  listDirsInDir,
  readFile,
  readUtf8File,
  readJsonFile,
  writeJsonFile,
  writeKeyFile,
  writeFile,
};
