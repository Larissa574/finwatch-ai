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
function statut_(email,etat,source) {
  const lock=LockService.getScriptLock();lock.waitLock(20000);
  try {
    const s=table_(), valeurs=s.getDataRange().getValues(); let ligne=0;
    for(let i=1;i<valeurs.length;i++) if(String(valeurs[i][0]).toLowerCase()===email) ligne=i+1;
    const old=ligne?valeurs[ligne-1]:null, maintenant=new Date().toISOString();
    const inscription=etat==='ACTIF' ? maintenant : (old ? old[2] : '');
    const retrait=etat==='DESINSCRIT' ? maintenant : '';
    const donnee=[email,etat,inscription,retrait,etat==='ACTIF'?source:(old?old[4]:'')];
    if(ligne) s.getRange(ligne,1,1,5).setValues([donnee]); else s.appendRow(donnee);
  } finally {lock.releaseLock();}
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
    let indices=[];
    for(let i=1;i<data.length;i++) {
      if(String(data[i][0]).trim().toLowerCase()===adresse) indices.push(i+1);
    }
    if(indices.length===0) return 'Cette adresse ne figure pas dans nos abonnements.';
    const maintenant=new Date().toISOString();
    // En cas de doublons historiques, tous sont désactivés.
    indices.forEach(function(i) {
      const old=data[i-1];
      s.getRange(i,1,1,5).setValues([[
        adresse,'DESINSCRIT',old[2],old[3]||maintenant,old[4]
      ]]);
    });
    return 'Votre désinscription a été confirmée. Vous ne recevrez plus les prochains bulletins FINWATCH AI.';
  } finally { lock.releaseLock(); }
}
