// Shared Android hardware-back bridge (Capacitor App plugin).
// Page scripts may define window.StudyReelBack(canGoBack) to take over the action.
(function(){
  const cap = window.Capacitor;
  let App = null;
  try{
    if(cap && typeof cap.registerPlugin==='function' && cap.isPluginAvailable && cap.isPluginAvailable('App')){
      App = cap.Plugins.App || cap.registerPlugin('App');
    }
  }catch(e){}

  window.StudyReelApp = App;
  window.StudyReelExit = function(){
    if(App && typeof App.exitApp==='function'){
      App.exitApp();
      return true;
    }
    return false;
  };

  if(App && typeof App.addListener==='function'){
    try{
      const pending = App.addListener('backButton', (info)=>{
        const canGoBack = !!(info && info.canGoBack);
        if(typeof window.StudyReelBack==='function'){
          window.StudyReelBack(canGoBack);
        } else if(canGoBack){
          window.history.back();
        } else {
          App.exitApp();
        }
      });
      if(pending && typeof pending.catch==='function') pending.catch(()=>{});
    }catch(e){}
  }
})();
