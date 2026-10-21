const fs = require('fs');  // required for file I/O
var argv = require('minimist')(process.argv.slice(2));

// Application to read romfile (binary) and convert this to FREQs

var romfile = "";
var prescale = 64;      // dont change
var local_osc = 21600;  // dont change
const TX = 0;
const RX = 1;
var binfile = "./roms/rom.bin";
//var binfile = "./VHF_Master.bin";

var debug = 0;

//var xtl = 6000; // (sawtron 999)
var xtl = 1500; // KG107 (eg VHF)

//var buffer = new ArrayBuffer(32);
//var chan = new Int8Array(buffer);  // Each Channel is 16 x 16 bit words

var chan = Buffer.alloc(32, "0xff");

if (Number(process.argv[2]) > 1) {
    binfile = argv['rom'];
    xtl = argv['xtl'];    
} else {
    console.log("--rom={romfile} | --xtl={VFO freq) Usually 6000 or 1500");
}

console.log("Read a Sawtron Binary File and display the programming to the console");
console.log("ARGS: %s", process.argv[2]);
console.log("Output File: %s", binfile);
console.log("Crystal Freq = %d Mhz",xtl/1000);

// Open the file 
console.log("Reading %s...", binfile);

var fbuffer = fs.readFileSync(binfile);
var lines = [];
var chanNo = 1;

for (let i = 0; i < fbuffer.length; i += 16) {
  let block = fbuffer.slice(i, i + 16) // cut buffer into blocks of 16
  //console.log("BIN:", block)
  getFreq(chanNo++,block);
  lines.push(block)
  //console.log("------------------------")
}

console.log("End of %s - Length 0x%s (%d) words", binfile, fbuffer.length.toString(16), fbuffer.length);

/*
let stream = fs.createReadStream(binfile);
let outputBuffer = "";
stream.on('data', (data) => {
    // you get an unknown length chunk of data from the file here in a Buffer object
    for (const val of data) {
        outputBuffer += convertToHex(val) + " ";
        //outputBuffer += val;
        if (outputBuffer.length = 16) {
            console.log("Line: ",outputBuffer);
            outputBuffer = "";
        }
    }
}).on('error', err => {
    // some sort of error reading the file
    console.log(err);
}).on('end', () => {
    // output any remaining buffer
    console.log("DONE");
    //console.log(outputBuffer);
});
//---------------------
*/


function convertToHex(val) {
    let str = val.toString(16);
    if (str.length < 2) {
        str = "0" + str;
    }
    return str.toUpperCase();
}
function getFreq(ch, chan) {

    var no_tx = false;

    // Dummy Data
    //chan = [0x01, 0x01, 0x0C, 0x01, 0x01, 0x00, 0x0F, 0x00, 0x01, 0x03, 0x09, 0x02, 0x01, 0x00, 0x0F, 0x00];

    //console.log(chan);
    if (chan[0] == '0xff')
        return;

    if (chan[9] == '0xff')
        no_tx = true; 

    let rx_A = new Array(2);
    let rx_N = new Array(3);
    let rx_R = new Array(3);
    let tx_A = new Array(2);
    let tx_N = new Array(3);
    let tx_R = new Array(3);

    // RX Information

    rx_A[0] = chan[1].toString(16);
    rx_A[1] = chan[0].toString(16);

    rx_N[0] = chan[4].toString(16);
    rx_N[1] = chan[3].toString(16);
    rx_N[2] = chan[2].toString(16);

    rx_R[0] = chan[7].toString(16);
    rx_R[1] = chan[6].toString(16);
    rx_R[2] = chan[5].toString(16);

    // TX information

    tx_A[0] = chan[9].toString(16);
    tx_A[1] = chan[8].toString(16);

    tx_N[0] = chan[12].toString(16);
    tx_N[1] = chan[11].toString(16);
    tx_N[2] = chan[10].toString(16);

    tx_R[0] = chan[15].toString(16);
    tx_R[1] = chan[14].toString(16);
    tx_R[2] = chan[13].toString(16);

    if (debug == 1) {
      console.log("RX (A) (N) (R): ", rx_A, rx_N, rx_R);
      console.log("TX (A) (N) (R): ", tx_A, tx_N, tx_R);
    }

    var rx_A_dec = parseInt(rx_A.join(''), 16);
    var rx_N_dec = parseInt(rx_N.join(''), 16);
    var rx_R_dec = parseInt(rx_R.join(''), 16);

    var tx_A_dec = parseInt(tx_A.join(''), 16);
    var tx_N_dec = parseInt(tx_N.join(''), 16);
    var tx_R_dec = parseInt(tx_R.join(''), 16);

    if (debug == 1) {
      console.log("RX DEC: ", rx_A_dec, rx_N_dec, rx_R_dec);
      console.log("TX DEC: ", tx_A_dec, tx_N_dec, tx_R_dec);
    }

    var spacing = xtl / rx_R_dec;


    /* Need to do the opposite of this:
    
      if (rx_mode) 
            offset = local_osc;  // RX requires that we subtract the LO freq
        d_param = (freq - offset) / spacing;     
        n_param = ~~(d_param / prescale);           // Quotient (could also use floor())
        a_param = d_param % prescale;               // Remainder
    */

    var d_param = (rx_N_dec * prescale) + rx_A_dec;  // (Quotient * presale) + remainder
    var rx_freq = (d_param * spacing) + local_osc;

    var d_param = (tx_N_dec * prescale) + tx_A_dec;  // (Quotient * presale) + remainder
    var tx_freq = (d_param * spacing);

    rx_freq = parseFloat(rx_freq/1000).toFixed(4);
    tx_freq = parseFloat(tx_freq/1000).toFixed(4);

    if (no_tx)
        tx_freq = "--Empty-- ";

    let bank =  ~~(ch/128);
    let ch_hex = ch.toString(16);
    let ch_disp = ch%128;

    console.log("%d-%d | RX: %s | TX: %s | Spacing %d kHz (0x%s)", 
                                            bank, ch_disp, rx_freq, tx_freq, spacing, ch_hex);
}