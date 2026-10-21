const fs = require('fs');  // required for file I/O
const path = require('path');
const csv = require('csv-parser');
var argv = require('minimist')(process.argv.slice(2));

var prescale = 64;          // dont change
var local_osc = 21600000;   // Hz (21.6 MHz) dont change
const TX = 0;
const RX = 1;

//var xtl = 6000; // (sawtron 999)
var xtl = 1500; // KG107 (eg VHF)

var debug = 0;

/* Mermory Stucture
 *
 * Each channel is 16 bytes long
 * Each bank is 128 * 16 bytes (the max addressable channels per bank is 99)
 * Total ROM is 4 banks * 128 chan slots * 16 bytes = 8192 bytes
 *
 * All frequency maths is done in whole Hz so that float rounding can never
 * put a channel one step low (eg 512.045 * 1000 = 512044.99999...).
 */

var rom = Buffer.alloc(8192, 0xff);

// Defaults are relative to the repo root (one level up from this script)
var csvfile = path.join(__dirname, "..", "data", "data.csv");
var romfile = path.join(__dirname, "..", "roms", "rom.bin");

var errors = [];
var rowNo = 1;    // header is line 1

//
// Main Program
//
console.log("Create BIN file for Kyodo / Sawtron UHF/VHF radio");

// Options work with or without the old leading "2" (eg: node writerom.js 2 --csv=...)
if (argv['csv'] !== undefined) csvfile = String(argv['csv']);
if (argv['rom'] !== undefined) romfile = String(argv['rom']);
if (argv['xtl'] !== undefined) xtl = Number(argv['xtl']);

if (argv['csv'] === undefined) {
    console.log("--csv={csvfile} | --rom={romfile} | --xtl={VFO freq) Usually 6000 or 1500");
}

console.log("Source File: %s", csvfile);
console.log("Rom Output File: %s", romfile);
console.log("Internal VFO Freq (6000 or 1500): %d", xtl);
console.log("-----------------------------------------------------------------");

console.log("Source File format: bank, channel, rx_freq, tx_freq, spacing");
console.log("Eg: 0, 23, 477.000, 476.000, 25");

console.log("-----------------------------------------------------------------");

if (!Number.isInteger(xtl * 1000) || xtl <= 0) {
    console.log("ERROR: --xtl must be a frequency in kHz (usually 6000 or 1500)");
    process.exit(1);
}
if (!fs.existsSync(csvfile)) {
    console.log("ERROR: CSV file %s not found", csvfile);
    process.exit(1);
}

// Also need to read in CSV file of freqs and use these to output to .bin file.
fs.createReadStream(csvfile)
  .pipe(csv())
  .on('data', (row) => {

    rowNo++;
    let bank = Number(row["bank"]);
    let channel = Number(row["channel"]);
    let rxf = row["rx_freq"];
    let txf = row["tx_freq"];
    let spacing = row["spacing"];

    let skip = false;

    // Sanity check the passed in arguments...

    // Check if the CSV line is suitable
    if (isNaN(bank) || isNaN(channel) || (rxf == 0)) {
        // Need to Skip
        skip = true;
    }

    // Check that the spacing is valid
    switch(Number(spacing)) {
        case 5:
        case 10:
        case 12.5:
        case 25:
        case 30:
            // These are all valid dont change skip
            break;
        default:
            skip = true;
    }

    // Calculate the buffer address
    let address = (bank * 128 * 16) + ((channel - 1)*16);

    // If this is a valid entry then process it
    if (skip === false) {

        console.log("Addr: 0x%s | Bank: %d | Ch: %d | RX: %s | TX: %s | Ch Sp: %s",
            address.toString(16).padStart(2, 0),
            bank, channel, rxf, txf, spacing);

        try {
            let full_ch = freq2bin(rxf, txf, spacing, xtl);

            // This is only needed if we want to print the string
            if (debug == 1) {
                let ch_buf = "";
                for (let i = 0; i < full_ch.length; i++) {
                    ch_buf += (full_ch[i].toString(16).padStart(2, 0));
                    ch_buf += " ";
                }
                console.log(ch_buf);  // Print the converted string XX XX XX XX XX XX XX XX XX....
            }

            rom.set(full_ch, address);
        } catch (err) {
            errors.push("line " + rowNo + " (bank " + bank + " ch " + channel + "): " + err.message);
        }

    } else {
        console.log("Skipped : Addr: 0x%s | Bank: %d | Ch: %d | RX: %s | TX: %s | Ch Sp: %s",
        address.toString(16).padStart(2, 0),
        bank, channel, rxf, txf, spacing);
    }


  })
  .on('end', () => {
    if (errors.length > 0) {
        console.log("-----------------------------------------------------------------");
        for (const e of errors)
            console.log("ERROR: %s", e);
        console.log("%d error(s) in %s - ROM NOT written", errors.length, csvfile);
        process.exitCode = 1;
        return;
    }
    console.log('%s successfully processed', csvfile);
    fs.writeFile((romfile), rom, function (err) {
        if (err) throw err;
        console.log('Saved %s', romfile);
      });
  });




// ---------- FUNCTIONS --------

function decimalToInt(text, scale, what) {

    // Exact decimal string -> integer, eg ("476.4125", 1000000) -> 476412500
    // Avoids float maths entirely.
    let str = String(text).trim();
    let digits = String(scale).length - 1;    // scale is a power of 10
    let m = str.match(/^(\d+)(?:\.(\d*))?$/);
    if (!m)
        throw new Error("'" + str + "' is not a valid " + what);
    let frac = (m[2] || "").replace(/0+$/, "");
    if (frac.length > digits)
        throw new Error("'" + str + "' has too many decimal places for a " + what);
    return Number(m[1]) * scale + Number(frac.padEnd(digits, "0") || 0);
}

function freq2bin (rxfreq, txfreq, step, xtl) {

    // Returns a 16 byte buffer of channel prog data: RX (8) | TX (8)

    let full_ch = Buffer.alloc(16, 0xff);
    let step_hz = decimalToInt(step, 1000, "channel spacing");   // kHz -> Hz
    let xtl_hz = Math.round(xtl * 1000);                          // kHz -> Hz

    let rx_data = get_channel_data(RX, decimalToInt(rxfreq, 1000000, "frequency"), step_hz, xtl_hz);
    full_ch.set(rx_data);

    if (txfreq > 0)
        full_ch.set(get_channel_data(TX, decimalToInt(txfreq, 1000000, "frequency"), step_hz, xtl_hz), 8);
    // else TX stays 0xff = receive only

    if (debug) {
        console.log("freq2bin(): ", full_ch);
    }

    return full_ch;
}

function to_nibbles(value, size) {

    // One hex digit per byte, least significant first
    // eg 0x08C (size 3) ==> 0C 08 00
    let nibbles = Buffer.alloc(size, 0);
    for (let i = 0; i < size; i++)
        nibbles[i] = (value >> (4 * i)) & 0x0f;
    return nibbles;
}

function fmt_mhz(hz) {
    return (hz / 1000000).toFixed(4);
}

function get_channel_data(rx_mode, freq, spacing, xtl) {

    // freq, spacing and xtl are all whole Hz
    var offset = 0;

    if (rx_mode)
        offset = local_osc;  // RX requires that we subtract the LO freq

    if (xtl % spacing !== 0)
        throw new Error((spacing / 1000) + " kHz spacing is not possible with a " + (xtl / 1000) + " kHz reference");

    if ((freq - offset) % spacing !== 0) {
        let below = freq - ((freq - offset) % spacing);
        throw new Error(fmt_mhz(freq) + " MHz is not on the " + (spacing / 1000) +
                        " kHz channel grid (nearest: " + fmt_mhz(below) + " or " + fmt_mhz(below + spacing) + ")");
    }

    let d_param = (freq - offset) / spacing;
    let n_param = Math.floor(d_param / prescale);   // Quotient
    let a_param = d_param % prescale;               // Remainder
    let r_param = xtl / spacing;                    // channel ratio

    if (d_param < 0 || n_param > 0xfff || r_param > 0xfff)
        throw new Error(fmt_mhz(freq) + " MHz is out of range for this radio");

    if (debug == true) {
        console.log("Freq: %d | Mode %s | Ch Space: %d | d: %d n: %d a: %d r: %d",
                                    freq, rx_mode ? "RX":"TX", spacing, d_param, n_param, a_param, r_param);
    }

    // Now return as A(2) N(3) R(3)
    // aa aa nn nn nn rr rr rr
    var chan_data = Buffer.alloc(8);
    chan_data.set(to_nibbles(a_param, 2));
    chan_data.set(to_nibbles(n_param, 3), 2);
    chan_data.set(to_nibbles(r_param, 3), 5);

    if (debug)
        console.log("chan_data: ", chan_data);

    return (chan_data);
}
