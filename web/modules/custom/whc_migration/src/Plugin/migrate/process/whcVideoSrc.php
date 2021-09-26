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
 *   id = "whcvideosrc"
 * )
 */
class whcVideoSrc extends ProcessPluginBase {
  /**
   * {@inheritdoc}
   */

  public function transform($value, MigrateExecutableInterface $migrate_executable, Row $row, $destination_property) {

    return $value['fid'];

  }
}