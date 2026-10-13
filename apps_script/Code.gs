// FINWATCH AI - application Web Google Apps Script
const ENTETES = ['email','statut','date_inscription','date_desinscription','source_consentement'];
function configuration_(cle) { const v=PropertiesService.getScriptProperties().getProperty(cle); if(!v) throw Error('Configuration absente : '+cle); return v; }
function table_() {
  const livre=SpreadsheetApp.openById(configuration_('SHEET_ID'));
  let s=livre.getSheetByName('Abonnes');
  if(!s){s=livre.insertSheet('Abonnes');s.appendRow(ENTETES);}
  if(s.getRange(1,1,1,5).getValues()[0].join('|')!==ENTETES.join('|')) throw Error('En-têtes Abonnes incorrects');
  return s;
}
function email_(value) { const s=String(value||'').trim().toLowerCase(); if(s.length>254||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)) throw Error('Adresse email invalide'); return s; }
function token_(email) {
  const bytes=Utilities.computeHmacSha256Signature(email,configuration_('FINWATCH_HMAC_SECRET'));
  return bytes.map(x=>('0'+(x&255).toString(16)).slice(-2)).join('');
}
function verifierToken_(a,b) { const t=token_(a); return /^[a-f0-9]{64}$/.test(String(b||'')) && t===b; }
function enregistrerStatutUnique_(s, email, etat, source) {
  const lignes=s.getDataRange().getValues();
  const correspondances=[];
  for(let i=1;i<lignes.length;i++) {
    if(String(lignes[i][0]).trim().toLowerCase()===email) correspondances.push(i+1);
  }
  const maintenant=new Date().toISOString();
  const lignePrincipale=correspondances.length ? correspondances[0] : null;
  const ancienne=lignePrincipale ? lignes[lignePrincipale-1] : null;
  const dateInscription=etat==='ACTIF' ? maintenant : (ancienne ? ancienne[2] : '');
  const dateDesinscription=etat==='DESINSCRIT' ? maintenant : '';
  const provenance=etat==='ACTIF' ? source : (ancienne ? ancienne[4] : '');
  const valeurs=[email,etat,dateInscription,dateDesinscription,provenance];
  if(lignePrincipale) {
    s.getRange(lignePrincipale,1,1,5).setValues([valeurs]);
    // Supprimer les doublons en partant du bas pour ne pas decaler les indices.
    correspondances.slice(1).reverse().forEach(function(numero){ s.deleteRow(numero); });
  } else {
    s.appendRow(valeurs);
  }
}
function statut_(email,etat,source) {
  const lock=LockService.getScriptLock();lock.waitLock(20000);
  try {
    enregistrerStatutUnique_(table_(),email,etat,source);
  } finally { lock.releaseLock(); }
}
function inscrire(email,consentement) {
  if(consentement!==true) throw Error('Consentement obligatoire');
  const e=email_(email);statut_(e,'ACTIF','formulaire web - accord explicite');
  return 'Votre inscription à FINWATCH AI a été enregistrée.';
}
// GET n'effectue jamais de modification : les robots des messageries suivent parfois les liens.
function doGet(e) {
  const p=e&&e.parameter||{};
  if(p.action==='unsubscribe') {
    let adresse='', jeton='', valide=false;
    try {
      adresse=email_(p.email);
      jeton=String(p.token||'');
      valide=verifierToken_(adresse,jeton);
    } catch(err) { valide=false; }
    const page=HtmlService.createTemplateFromFile('Desinscription');
    page.adresse=valide ? adresse : '';
    page.jeton=valide ? jeton : '';
    page.valide=valide;
    return page.evaluate().setTitle('FINWATCH AI — Se désabonner');
  }
  return HtmlService.createTemplateFromFile('Index').evaluate().setTitle('FINWATCH AI — Newsletter');
}

// Uniquement appelée après action explicite sur le bouton de confirmation.
function confirmerDesinscription(email,jeton) {
  const adresse=email_(email);
  if(!verifierToken_(adresse,jeton)) throw Error('Lien de désinscription invalide.');
  const lock=LockService.getScriptLock();lock.waitLock(20000);
  try {
    const s=table_(), data=s.getDataRange().getValues();
    const existe=data.slice(1).some(function(ligne) {
      return String(ligne[0]).trim().toLowerCase()===adresse;
    });
    if(!existe) return 'Cette adresse ne figure pas dans nos abonnements.';
    enregistrerStatutUnique_(s,adresse,'DESINSCRIT','');
    return 'Votre désinscription a été confirmée. Vous ne recevrez plus les prochains bulletins FINWATCH AI.';
  } finally { lock.releaseLock(); }
}
