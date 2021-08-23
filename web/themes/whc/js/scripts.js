document.addEventListener( 'DOMContentLoaded', function () {
  new Splide( '.splide', {pagination: false} ).mount();
} );


(function($) {

  // Quick hack to allow slideshow to render.
  $(window).one('scroll', function() {
    $( "#slideclick" ).removeAttr("open");
  });

  // Function to loop through classes and add ids.
  function addVideoAttr(classToFind, attribute, valToAdd) {

    var video_thumb = $(classToFind);
    var i = 0;
    $(video_thumb).each(function(index) {
      i++;
      $(this).attr(attribute, valToAdd + i);
    });

  }

  $(document).ready(function(){

    // JS that controlls the tabs.
    // Go through and add Ids
    addVideoAttr('.video_thumb', 'href', '#video_box_');
    addVideoAttr('.content-videos--info', 'id', 'video_box_');

    $('.content-videos--nav').each(function(){
      // For each set of tabs, we want to keep track of
      // which tab is active and its associated content
      var $active, $content, $links = $(this).find('a');
    
      // If the location.hash matches one of the links, use that as the active tab.
      // If no match is found, use the first link as the initial active tab.
      $active = $($links.filter('[href="'+location.hash+'"]')[0] || $links[0]);
      $active.addClass('active');
    
      $content = $($active[0].hash);
    
      // Hide the remaining content
      $links.not($active).each(function () {
        $(this.hash).hide();
      });
    
      // Bind the click event handler
      $(this).on('click', 'a', function(e){
        // Make the old tab inactive.
        $active.removeClass('active');
        $content.hide();
    
        // Update the variables with the new link and content
        $active = $(this);
        $content = $(this.hash);
    
        // Make the tab active.
        $active.addClass('active');
        $content.show();
    
        // Prevent the anchor's default click action
        e.preventDefault();
      });
    });


    
  });
}(jQuery));
