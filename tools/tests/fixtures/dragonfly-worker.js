var status_mods = {
   none: 1,
   psn: 1.5,
   par: 1.5,
   brn: 1.5,
   slp: 2.5,
   frz: 2.5
};
var gvals = [1229/4096, 0.5, 2867/4096, 3277/4096, 3686/4096, 1];
var pvals = [0, 0.5, 1, 1.5, 2, 2.5];

function isUltraBeast(pokemon) {
   return pokemon >= 793 && pokemon <= 799 || pokemon >= 803 && pokemon <= 806;
}

function inArray(item, array) {
   for (var i = 0; i < array.length; i++) {
      if (array[i] === item) {
         return true;
      }
   }
   return false;
}

function getBallBonus(event) {
   // If it's an Ultra Beast, then everything except Beast Balls and Master Balls has a ball bonus of 0.1x (410/4096).
   if (isUltraBeast(event.pokemon.id) && event.ball !== 'beast-ball' && event.ball !== 'master-ball') {
      return 410/4096;
   }

   switch (event.ball) {
      case 'great-ball':
      case 'safari-ball':
         return 1.5;
      case 'ultra-ball':
         return 2;
      case 'master-ball':
      case 'dream-ball':
         return -1;
      case 'net-ball':
         if (event.water_bug) {
            return (event.version_group >= 17 ? 3.5 : 3);
         }
         else {
            return 1;
         }
      case 'nest-ball':
         if (event.level < 30) {
            return Math.max(1, (41 - event.level) / 10);
         } else {
            return 1;
         }
      case 'dive-ball':
         if (event.underwater) {
            return 3.5;
         }
         else {
            return 1;
         }
      case 'repeat-ball':
         if (event.registered) {
            return (event.version_group >= 17 ? 3.5 : 3);
         }
         else {
            return 1;
         }
      case 'timer-ball':
         return Math.min(4, 1 + (event.turn - 1) * 1229/4096);
      case 'quick-ball':
         if (event.turn === 1) {
            return 5;
         }
         else {
            return 1;
         }
      case 'dusk-ball':
         if (event.dark) {
            return (event.version_group >= 17 ? 3 : 3.5);
         }
         else {
            return 1;
         }
      case 'fast-ball':
         if (event.pokemon.speed >= 100) {
            return 4;
         }
         else {
            return 1;
         }
      case 'level-ball':
         if (Math.floor(event.your_level / 4) >= event.level) {
            return 8;
         }
         else if (Math.floor(event.your_level / 2) >= event.level) {
            return 4;
         }
         else if (event.your_level > event.level) {
            return 2;
         }
         else {
            return 1;
         }
      case 'love-ball':
         if (event.your_pokemon === event.pokemon.id && (event.gender === "male" && event.your_gender === "female" || event.gender === "female" && event.your_gender === "male")) {
            return 8;
         }
         else {
            return 1;
         }
      case 'lure-ball':
         if (event.fishing) {
            return (event.version_group >= 17 ? 5 : 3);
         }
         else {
            return 1;
         }
      case 'moon-ball':
         // Nidorina, Nidorino, Clefairy, Jigglypuff, Skitty, Munna
         if ([30, 33, 35, 39, 300, 517].indexOf(event.pokemon.id) !== -1) {
            return 4;
         }
         else {
            return 1;
         }
      case 'beast-ball':
         if (isUltraBeast(event.pokemon.id)) {
            return 5;
         }
         else {
            return 410/4096;
         }
      default:
         return 1;
   }
}

function getDexCat(event) {
   var dexcat = 0;
   if (event.pokedex > 30) {
      dexcat++;
   }
   if (event.pokedex > 150) {
      dexcat++;
   }
   if (event.pokedex > 300) {
      dexcat++;
   }
   if (event.pokedex > 450) {
      dexcat++;
   }
   if (event.pokedex > 600) {
      dexcat++;
   }
   return dexcat;
}

function down(x) {
   // Rounds down to the nearest 1/4096th
   return Math.floor(x * 4096) / 4096;
}

function round(x) {
   // Rounds to the nearest 1/4096th
   return Math.round(x * 4096) / 4096;
}

function calcX(event) {
   var c = event.pokemon.catch_rate;

   if (event.ball === 'heavy-ball') {
      var weight = event.pokemon.weight;
      if (weight >= 3000) {
         c += 30;
      }
      else if (weight >= 2000) {
         c += 20;
      }
      else if (weight < 1000) {
         c -= 20;
      }
   }
   c = Math.min(255, Math.max(event.version_group >= 18 ? 1 : 0, c));

   var b = getBallBonus(event);
   if (b === -1) {
      return 256;
   }
   var s = status_mods[event.status];
   var m = event.max_hp;
   var h = event.cur_hp;

   var g = event.thickgrass ? gvals[getDexCat(event)] : 1;
   var e = event.entralink;

   console.log(c, b, s, m, h);

   return Math.min(255, down(round(down(round(round((3 * m - 2 * h) * g) * c * b) / (3 * m)) * s) * e / 100));
}

function calculateResults(event) {
   var x = calcX(event);
   if (x >= 256) {
      // Auto-catch
      return {
         success: 1,
         wobbles: [0, 0, 0, 0]
      };
   }

   // Using the full formula for Y
   var y = x === 0 ? 0 : Math.floor(round(65536 / round(Math.pow(round(255 / x), 3 / 16))));
   var y_chance = y / 65536;
   if (y_chance > 1) {
      // A chance greater than 100% is nonsensical, so bump it back down
      y_chance = 1;
   }
   var y_compl = 1 - y_chance;

   // Check for a critical capture
   var p = pvals[getDexCat(event)];
   var cc = Math.floor(round(round(x * p) / 6));

   var crit_chance = Math.min(1, cc / 256); // Can't have a better than 100% chance of a critical capture...

   var success_chance = Math.pow(y_chance, 4);
   return {
      success: success_chance,
      wobbles: [
         y_compl,
         y_chance * y_compl,
         Math.pow(y_chance, 2) * y_compl,
         Math.pow(y_chance, 3) * y_compl
      ],
      critical: crit_chance,
      crit_success: y_chance
   };
}

onmessage = function(event) {
   console.log("Worker received message", event.data);
   postMessage(calculateResults(event.data));
   close();
}