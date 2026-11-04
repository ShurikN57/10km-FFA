// Charge core.js (script navigateur sans exports) dans un contexte isolé
// et renvoie ses fonctions globales pour les tests Node.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

module.exports = function loadCore() {
  const src = fs.readFileSync(path.join(__dirname, '..', 'core.js'), 'utf8');
  const context = vm.createContext({ console, Intl, Date, Map, Set, URL });
  // Les déclarations `const` de haut niveau ne deviennent pas des propriétés
  // du contexte : on les exporte explicitement.
  vm.runInContext(src + '\n;this.FFA_SEASON_CATEGORY_AGES = FFA_SEASON_CATEGORY_AGES;', context);
  return context;
};
