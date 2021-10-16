(function($) {

  // This is to intalize slideshow.
  $(window).on('beforeunload', function() {
      $(window).scrollTop(0);
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

    $('.slideshow').slick({
      arrows: true,
      slidesToShow: 1,
      slidesToScroll: 1,
      dots: false,
      infinite: true,
      adaptiveHeight: false,
    });

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

    setTimeout(function() {
      $( "#slideclick" ).click();
    }, 1500);

    $('h2:contains("Search results")').css("display", "none");
    // acordian click

    setTimeout(function() {
      $('details').on('click', function(e){
        var allDetails = $( "details" );

        $(".slick-next, .slick-prev").click(function(e){
          e.stopPropagation(); 
        });

        if($(this).is("[open]")) {
          e.preventDefault();
          $(this).removeAttr("open");
        } else {
          $( ".content-details" ).find( allDetails ).removeAttr("open");
        }
      });
    }, 705);

    // Jump link auto expand.
    $('#doc-text-img').on('click', function(){
      if ($('#doc_transcription').length) {
        $("#doc_transcription").click();
      } else {
        $("#doc-text").click();
        location.hash = "doc-text";
      }
    });
    
    $('#doc-text-icon').on('click', function(){
      $("#doc-text").click();
    });


});

}(jQuery));
