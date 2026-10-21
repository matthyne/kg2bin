const fs = require('fs');  // required for file I/O
const csv = require('csv-parser');
var argv = require('minimist')(process.argv.slice(2));

var prescale = 64;      // dont change
var local_osc = 21600;  // dont change
var result = 0;
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
 */

var full_ch = Buffer.alloc(16, 0xff);
var rom = Buffer.alloc(8192, 0xff);

var csvfile = "./data/data.csv";
var romfile = "./roms/rom.bin"

var cnt = 0;

//
// Main Program
//
console.log("Create BIN file for Kyodo / Sawtron UHF/VHF radio");

if (Number(process.argv[2]) > 1) {
    console.log(argv);
    csvfile = argv['csv'];
    romfile = argv['rom'];
    xtl = argv['xtl'];
} else {
    console.log("--csv={csvfile} | --rom={romfile} | --xtl={VFO freq) Usually 6000 or 1500");
}

console.log("Source File: %s", csvfile);
console.log("Rom Output File: %s", romfile);
console.log("Internal VFO Freq (6000 or 1500): %d", xtl);
console.log("-----------------------------------------------------------------");

console.log("Source File format: bank, channel #, rx_freq, tx_freq, spacing");
console.log("Eg: 0, 23, 477.000, 476.000, 25");

console.log("-----------------------------------------------------------------");



// Also need to read in CSV file of freqs and use these to output to .bin file.
fs.createReadStream(csvfile)
  .pipe(csv())
  .on('data', (row) => {

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

        //   console.log("---------");
        console.log("Addr: 0x%s | Bank: %d | Ch: %d | RX: %s | TX: %s | Ch Sp: %s",
            address.toString(16).padStart(2, 0),
            bank, channel, rxf, txf, spacing);

        full_ch = freq2bin(rxf, txf, spacing, xtl);

        //console.log(full_ch);

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

    } else {
        console.log("Skipped : Addr: 0x%s | Bank: %d | Ch: %d | RX: %s | TX: %s | Ch Sp: %s",
        address.toString(16).padStart(2, 0),
        bank, channel, rxf, txf, spacing);
    }


  })
  .on('end', () => {
    console.log('%s successfully processed', csvfile);
    //console.log(rom);
    fs.writeFile((romfile), rom, function (err) {
        if (err) throw err;
        console.log('Saved %s', romfile);
      });
  });




// ---------- FUNCTIONS --------

function freq2bin (rxfreq, txfreq, step, xtl) {

    // Returns an array of channel prog data for a freq

    let txdata = Buffer.alloc(8); // new Int16Array(8);
    let rxdata = Buffer.alloc(8);  //new Int16Array(8);

    if (rxfreq > 0)
        rx_data = get_channel_data(RX, rxfreq*1000, step, xtl);
    else
        rx_data = [0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff];

    if (txfreq > 0)
        tx_data = get_channel_data(TX, txfreq*1000, step, xtl);
    else
        tx_data = [0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff];


    if (debug) {
        console.log("freq2bin(): RXD: ",rx_data);
        console.log("freq2bin(): TXD: ",tx_data);
    }

    // Copy this to one big array rx | tx
    full_ch.set(rx_data);
    full_ch.set(tx_data, rx_data.length);

    return full_ch;
}

function ad_conv(dec, size) {

    //hexarray = new Int16Array(size);  // 2 or 3 16 bit spots
    var hexarray = Buffer.alloc(size,0);
    var debug = 0;

    // eg:  140 = 08C ==> 0C 08 00
    // eg   XYZ = 0Z 0Y 0X
    var hex = dec.toString(16);

    // Make sure all numbers are XYZ
    if (dec < 256)
    hex = "0" + hex;

    if (dec < 16)
    hex = "0" + hex;

    // Split XYX into X Y Z
    // convert to HEX number.

    if (size == 2) {
        hexarray[0] = parseInt(hex.charAt(2),16);
        hexarray[1] = parseInt(hex.charAt(1),16);
    } else {
        hexarray[0] = parseInt(hex.charAt(2),16);
        hexarray[1] = parseInt(hex.charAt(1),16);
        hexarray[2] = parseInt(hex.charAt(0),16);
        //console.log("charAt: ",hex.charAt(0), hex.charAt(1), hex.charAt(2));
    }
    if (debug) {
        console.log("ad_conv(): dec: %d ==> hex: %s (size: %d) ", dec, hex, size);
        console.log("ad_conv(): ", hexarray);
    }
    return hexarray;
}

function get_channel_data(rx_mode, freq, spacing, xtl) {

    var offset = 0;
    var debug = 0;

    if (rx_mode)
        offset = local_osc;  // RX requires that we subtract the LO freq
    d_param = (freq - offset) / spacing;
    n_param = ~~(d_param / prescale);           // Quotient (could also use floor())
    a_param = d_param % prescale;               // Remainder

    r_param = xtl / spacing;       // channel ratio

    if (debug == true) {
        console.log("Freq: %d | Mode %s | Ch Space: %d | d: %d n: %d a: %d r: %d",
                                    freq, rx_mode ? "RX":"TX", spacing, d_param, n_param, a_param, r_param);
    }

    /* Convert to HEX (or the KG's version of it) */
    a_hex = ad_conv(a_param, 2);    // 2 bytes
    n_hex = ad_conv(n_param, 3);    // 3 bytes
    r_hex = ad_conv(r_param, 3);    // 3 bytes

    // Return as byte String...
    // aa aa nn nn nn rr rr
    if (debug) {
        console.log("a: ", a_hex);
        console.log("n: ", n_hex);
        console.log("r: ",r_hex);
    }
    // console.log("\n\n");

    //chan_data = new Int16Array(8);
    var chan_data = Buffer.alloc(8);

    // Now return string as A(2) N(3) R(3)
    // Copy this to one big array
    // aa aa nn nn nn rr rr rr
    chan_data.set(a_hex);
    chan_data.set(n_hex, a_hex.length);
    chan_data.set(r_hex, a_hex.length + n_hex.length);


    if (debug)
        console.log("chan_data: ", chan_data);

    return (chan_data);
}