<?php

use Drupal\node\Entity\Node;
use Drupal\paragraphs\Entity\Paragraph;

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
    $l['data'][$key]['thumbnail_fid'] = $thumbnail_data['field_video_thumbnail_fid'];
    $l['data'][$key]['youtube_link'] = $youtube_data['field_youtube_link_input'];
    $l['data'][$key]['video_clip_fid'] = $video_clip_data['field_video_clips_fid'];
    $l['data'][$key]['transcript'] =  $transcript_data['field_video_clip_transcripts_value'];

    $video_series = $l;

  }

  return $video_series;
}

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

  if ($video_data) {
    foreach ($video_data['data'] as $video) {

      // Create paragraph.
      \Drupal\Core\Database\Database::setActiveConnection();

      $paragraph = Paragraph::create(['type' => 'video',]);
      $paragraph->set('field_video_thumbnail', $video['thumbnail_fid']);
      $paragraph->set('field_youtube_link', $video['youtube_link']);
      $paragraph->set('field_video_clip', $video['video_clip_fid']);
      $paragraph->set('field_video_clip_transcript', $video['transcript']); 
      $paragraph->save();

      $data = $node->get('field_video_clip')->getValue();
      $data[] = array(
        'target_id' => $paragraph->id(),
        'target_revision_id' => $paragraph->getRevisionId(),
      );
      $node->set('field_video_clip', $data);
    }

    // Save Node.
    echo 'Node: ' . $nid . ' was updated' . PHP_EOL;
    $node->set('field_video_series_transcript', $video_data['transcript_dl_fid']);
    $node->save();
  }

}

