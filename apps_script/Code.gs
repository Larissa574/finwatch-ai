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
function doGet(e) {
  const p=e&&e.parameter||{};
  if(p.action==='unsubscribe') {
    let message='Lien de désinscription invalide.';
    try { const mail=email_(p.email);if(verifierToken_(mail,p.token)){statut_(mail,'DESINSCRIT','');message='Votre désinscription à FINWATCH AI a été prise en compte.';} }
    catch(err){message='Impossible de traiter cette demande.';}
    return HtmlService.createHtmlOutput('<!doctype html><html lang="fr"><meta charset="utf-8"><body style="font:17px Arial;margin:60px auto;max-width:620px"><h1>FINWATCH AI</h1><p>'+message+'</p></body></html>');
  }
  return HtmlService.createTemplateFromFile('Index').evaluate().setTitle('FINWATCH AI — Newsletter');
}