<?php

namespace Drupal\whc_migration\Plugin\migrate\process;

use Drupal\migrate\ProcessPluginBase;
use Drupal\migrate\MigrateException;
use Drupal\migrate\MigrateExecutableInterface;
use Drupal\migrate\Row;

/**
 * This plugin extracts raw youtube link value.
 *
 * @MigrateProcessPlugin(
 *   id = "whcyoutubelink"
 * )
 */
class whcYoutubeLink extends ProcessPluginBase {
  /**
   * {@inheritdoc}
   */

  public function transform($value, MigrateExecutableInterface $migrate_executable, Row $row, $destination_property) {
  
    // Get source url for YouTube videos.
    if ($destination_property == 'field_youtube_video') {

      $link = $value['input'];
      return $value['value'] = $link;
      
    }

  }
}