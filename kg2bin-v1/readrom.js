const fs = require('fs');  // required for file I/O
const path = require('path');
var argv = require('minimist')(process.argv.slice(2));

// Application to read romfile (binary) and convert this to FREQs

var prescale = 64;          // dont change
var local_osc = 21600000;   // Hz (21.6 MHz) dont change
var valid_steps = [5, 10, 12.5, 25, 30];   // kHz

// Default is relative to the repo root (one level up from this script)
var binfile = path.join(__dirname, "..", "roms", "rom.bin");

var debug = 0;

//var xtl = 6000; // (sawtron 999)
var xtl = 1500; // KG107 (eg VHF)

// Options work with or without the old leading "2" (eg: node readrom.js 2 --rom=...)
if (argv['rom'] !== undefined) binfile = String(argv['rom']);
if (argv['xtl'] !== undefined) xtl = Number(argv['xtl']);

if (argv['rom'] === undefined) {
    console.log("--rom={romfile} | --xtl={VFO freq) Usually 6000 or 1500");
}

console.log("Read a Sawtron Binary File and display the programming to the console");
console.log("ROM File: %s", binfile);
console.log("Crystal Freq = %d Mhz",xtl/1000);

if (!(xtl > 0)) {
    console.log("ERROR: --xtl must be a frequency in kHz (usually 6000 or 1500)");
    process.exit(1);
}
if (!fs.existsSync(binfile)) {
    console.log("ERROR: ROM file %s not found", binfile);
    process.exit(1);
}

// Open the file
console.log("Reading %s...", binfile);

var fbuffer = fs.readFileSync(binfile);
var problems = 0;

for (let i = 0; i < fbuffer.length; i += 16) {
  let block = fbuffer.slice(i, i + 16) // cut buffer into blocks of 16
  getFreq(i / 16, block);
}

console.log("End of %s - Length 0x%s (%d) bytes", binfile, fbuffer.length.toString(16), fbuffer.length);
if (problems > 0)
    console.log("WARNING: %d corrupt channel record(s) - see CORRUPT lines above", problems);


function from_nibbles(bytes) {
    // One hex digit per byte, least significant first: 0C 08 00 ==> 0x08C
    let value = 0;
    for (let i = 0; i < bytes.length; i++)
        value += bytes[i] << (4 * i);
    return value;
}

function decodeHalf(half, offset) {

    // Returns { freq (Hz), step (kHz) } for one RX or TX half (A(2) N(3) R(3))
    // or an { error } string if the record can't be valid.

    for (const b of half)
        if (b > 0x0f)
            return { error: "bytes are not nibbles (>0x0F)" };

    let a = from_nibbles(half.slice(0, 2));
    let n = from_nibbles(half.slice(2, 5));
    let r = from_nibbles(half.slice(5, 8));

    if (debug == 1)
        console.log("A: %d N: %d R: %d", a, n, r);

    if (r == 0)
        return { error: "reference divider R is 0" };

    let step = xtl / r;                     // kHz
    if (!valid_steps.includes(step))
        return { error: "step " + step + " kHz is not valid for a " + xtl + " kHz reference" };

    let d_param = (n * prescale) + a;       // (Quotient * prescale) + remainder
    let freq = Math.round(d_param * step * 1000) + offset;   // exact: step is a multiple of 0.5 kHz
    return { freq: freq, step: step };
}

function getFreq(slot, chan) {

    // slot is the 0-based record number in the file
    let bank = Math.floor(slot / 128);
    let ch_disp = (slot % 128) + 1;
    let ch_hex = (slot + 1).toString(16);
    let label = bank + "-" + ch_disp;

    if (chan.every(b => b == 0xff))
        return;     // empty slot

    let rx = (chan[0] == 0xff) ? { error: "RX half is empty but TX is set" }
                               : decodeHalf(chan.slice(0, 8), local_osc);
    let tx_empty = chan.slice(8, 16).every(b => b == 0xff);
    let tx = tx_empty ? null : decodeHalf(chan.slice(8, 16), 0);

    let error = rx.error ? "RX " + rx.error : (tx && tx.error) ? "TX " + tx.error : null;
    if (!error && tx && tx.step != rx.step)
        error = "RX/TX steps differ (" + rx.step + " vs " + tx.step + " kHz)";

    if (error) {
        problems++;
        console.log("%s | CORRUPT: %s (offset 0x%s)", label, error, (slot * 16).toString(16));
        return;
    }

    let rx_freq = (rx.freq / 1000000).toFixed(4);
    let tx_freq = tx_empty ? "--Empty-- " : (tx.freq / 1000000).toFixed(4);

    console.log("%s | RX: %s | TX: %s | Spacing %d kHz (0x%s)",
                                            label, rx_freq, tx_freq, rx.step, ch_hex);
}
