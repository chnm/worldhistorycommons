<?php

namespace Drupal\whc_migration\Plugin\migrate\process;

use Drupal\migrate\ProcessPluginBase;
use Drupal\migrate\MigrateException;
use Drupal\migrate\MigrateExecutableInterface;
use Drupal\migrate\Row;

/**
 * This plugin checks to see if node should be featured to the homepage.
 *
 * @MigrateProcessPlugin(
 *   id = "whcvideo"
 * )
 */
class whcVideo extends ProcessPluginBase {
  /**
   * {@inheritdoc}
   */

  public function transform($value, MigrateExecutableInterface $migrate_executable, Row $row, $destination_property) {


  // Here we create a new array for each video. Then in another plugin save the data.
    // print_r($value['value']);

    $field_collection_id = $value['value'];
    
    \Drupal\Core\Database\Database::setActiveConnection('drupal_7');
    $db = \Drupal\Core\Database\Database::getConnection();

    $query = $db->select('field_data_field_video_clip_transcripts', 'vct');
    $query->condition('vct.entity_id', $field_collection_id, '=');
    $query->fields('vct', ['field_video_clip_transcripts_value']);
    $result = $query->execute();

    $video = array();
    $record = $result->fetchAssoc();

    print_r($record);
    


    // foreach ($result as $record) {
    //   // Do something with each $record.
    //   // $record = $result->fetchAssoc();
    
    //   print_r($record);
    // }

// // // $query->fields('vct', array('entity_id', 'field_video_clip_transcripts_value'));
// // // // $query->join('node', 'n', 'n.uid = u.uid');
// // // // $query->orderBy('uid');
// // // $apple = $query->execute();
// // //     // $query = $db->query("SELECT field_video_clip_transcripts_value FROM {field_data_field_video_clip_transcripts} WHERE entity_id = :entity_id", [
// // //     //   ':created' => $field_collection_id,
// // //     // ]);
// // //     // $result = $query->fetchAll();

// //     print_r($apple);
//     \Drupal\Core\Database\Database::setActiveConnection();

  

  }
}