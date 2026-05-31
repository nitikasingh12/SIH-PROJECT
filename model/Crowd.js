const mongoose = require('mongoose');

const crowdSchema = new mongoose.Schema({
  zone: {
    type: String,
    required: true
  },
  count: {
    type: Number,
    required: true
  },
  maxCapacity: {
    type: Number,
    required: true
  },
  timestamp: {
    type: Date,
    default: Date.now
  }
});

module.exports = mongoose.model('Crowd', crowdSchema);