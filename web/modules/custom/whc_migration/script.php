<?php


use Drupal\node\Entity\Node;
use Drupal\media\Entity\Media;
use Drupal\file\Entity\File;
use Drupal\paragraphs\Entity\Paragraph;
use Drupal\taxonomy\Entity\Term;
use Drupal\block\Entity\Block;
use Drupal\block_content\Entity\BlockContent;
use Symfony\Component\Validator\Constraints\NotNull;

#TODO: copy this to make paragraph with values.
# https://drupal.stackexchange.com/questions/278476/paragraphs-from-sub-process
# https://drupal.stackexchange.com/questions/144947/how-do-i-access-a-field-value-for-an-entity-e-g-node-object


// Function that uses the legacy entity id and builds an array.
function getVideoData($entity_id) {

  \Drupal\Core\Database\Database::setActiveConnection('drupal_7');
  $db = \Drupal\Core\Database\Database::getConnection();

  $video_series_data = $db->query("SELECT field_video_clip_transcripts_value FROM {field_data_field_video_clip_transcripts} vct WHERE entity_id = :entity_id", [":entity_id" => $entity_id]);

  $video_series = array();
  foreach ($video_series_data as $key => $record) {

    // Video Thumbnail.
    $thumbnail_data = $db->query("SELECT field_video_thumbnail_fid FROM {field_data_field_video_thumbnail} vct WHERE entity_id = :entity_id AND delta = :delta", 
    [":entity_id" => $entity_id, ":delta" => $key,])->fetchAssoc();
    
    // Youtube Link
    $youtube_data = $db->query("SELECT field_youtube_link_input FROM {field_data_field_youtube_link} vct WHERE entity_id = :entity_id AND delta = :delta", 
    [":entity_id" => $entity_id, ":delta" => $key,])->fetchAssoc();
    
    // Clip video
    $video_clip_data = $db->query("SELECT field_video_clips_fid FROM {field_data_field_video_clips} vct WHERE entity_id = :entity_id AND delta = :delta", 
    [":entity_id" => $entity_id, ":delta" => $key,])->fetchAssoc();
    
    // Clip transcript
    $transcript_data = $db->query("SELECT field_video_clip_transcripts_value FROM {field_data_field_video_clip_transcripts} vct WHERE entity_id = :entity_id AND delta = :delta", 
    [":entity_id" => $entity_id, ":delta" => $key,])->fetchAssoc();
    
    // Transcript DL Link
    $transcript_dl_data = $db->query("SELECT field_video_clip_transcripts_dow_fid FROM {field_data_field_video_clip_transcripts_dow} vct WHERE entity_id = :entity_id", 
    [":entity_id" => $entity_id,])->fetchAssoc();

    // Build array.
    $l['transcript_dl_fid'] = $transcript_dl_data['field_video_clip_transcripts_dow_fid'];
    $l['entity_id'] = $entity_id;
    $l[$key]['thumbnail_fid'] = $thumbnail_data['field_video_thumbnail_fid'];
    $l[$key]['youtube_link'] = $youtube_data['field_youtube_link_input'];
    $l[$key]['video_clip_fid'] = $video_clip_data['field_video_clips_fid'];
    $l[$key]['transcript'] =  $transcript_data['field_video_clip_transcripts_value'];

    $video_series = $l;

  }

  return $video_series;
}

// --- Notes
// Logic here will need to be to create
// First go through all nodes (methods) and find that have a value in field_legacy_vid. 
// That becomes our entity ID, we then loop through each of that and we are good. 
// to which we then run the following script, build the array and save to paragraph.
// -- End Notes.

// Get list of nodes with a value in field_legacy_vid.
$query = \Drupal::entityQuery('node')
  ->condition('type', 'methods')
  ->condition('field_legacy_vid', NULL, 'IS NOT NULL');
$nids = $query->execute();

foreach ($nids as $nid) {
  
  // Load node, get Id, build video array.
  $node = Node::load($nid);
  $legacy_id = $node->get('field_legacy_vid')->getString();
  $video_data = getVideoData($legacy_id);

  // Create paragraph.
  \Drupal\Core\Database\Database::setActiveConnection();

  // save paragarph
  // save node.
  


  print_r($video_data);

}

// Loop through each nid and load the node.

// print_r($nids);



// print_r($video_series);


