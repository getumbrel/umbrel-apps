/* eslint-disable no-magic-numbers */
function NodeError(message, statusCode) {
  Error.captureStackTrace(this, this.constructor);
  this.name = this.constructor.name;
  this.message = message;
  this.statusCode = statusCode;
}
require("util").inherits(NodeError, Error);

function BitcoindError(message, error, statusCode) {
  Error.captureStackTrace(this, this.constructor);
  this.name = this.constructor.name;
  this.message = message;
  this.error = error;
  this.statusCode = statusCode;
}
require("util").inherits(BitcoindError, Error);

function LightningError(message, error, statusCode) {
  Error.captureStackTrace(this, this.constructor);
  this.name = this.constructor.name;
  this.message = message;
  this.error = error;
  this.statusCode = statusCode;
}
require("util").inherits(LightningError, Error);

function ValidationError(message, statusCode) {
  Error.captureStackTrace(this, this.constructor);
  this.name = this.constructor.name;
  this.message = message;
  this.statusCode = statusCode || 400;
}
require("util").inherits(ValidationError, Error);

module.exports = {
  NodeError,
  BitcoindError,
  LightningError,
  ValidationError,
};
