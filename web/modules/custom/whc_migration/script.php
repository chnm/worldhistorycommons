<?php
\Drupal\Core\Database\Database::setActiveConnection('drupal_7');
$db = \Drupal\Core\Database\Database::getConnection();

$entity_id = 134;
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
  // $l[$key] = array();
  $l[$key]['thumbnail_fid'] = $thumbnail_data['field_video_thumbnail_fid'];
  $l[$key]['youtube_link'] = $youtube_data['field_youtube_link_input'];
  $l[$key]['video_clip_fid'] = $video_clip_data['field_video_clips_fid'];
  $l[$key]['transcript'] =  $transcript_data['field_video_clip_transcripts_value'];


  $video_series = $l;

  // print_r($record);
}

print_r($video_series);
